//! Git operations via the `git` CLI.
//!
//! Uses subprocess calls instead of libgit2: no C dependency, fully
//! Send + Sync, and behaves identically to what a human would run.

use anyhow::{bail, Result};
use std::path::PathBuf;
use tokio::process::Command;
use tracing::{debug, info};

use crate::agent::Experiment;

pub struct GitOps {
    workspace: PathBuf,
}

impl GitOps {
    pub async fn new(workspace: &str) -> Result<Self> {
        let workspace = PathBuf::from(workspace);
        tokio::fs::create_dir_all(&workspace).await?;

        let ops = Self { workspace };

        if !ops.workspace.join(".git").exists() {
            info!("Initializing new git repository in {:?}", ops.workspace);
            ops.git(&["init"]).await?;
            ops.git(&["config", "user.email", "autoclaw@localhost"])
                .await?;
            ops.git(&["config", "user.name", "Autoclaw"]).await?;
            // An initial commit gives every later operation a HEAD to build on.
            ops.git(&["add", "-A"]).await?;
            let _ = ops
                .git(&["commit", "--allow-empty", "-m", "autoclaw: initial state"])
                .await;
        }

        Ok(ops)
    }

    async fn git(&self, args: &[&str]) -> Result<String> {
        let output = Command::new("git")
            .args(args)
            .current_dir(&self.workspace)
            .output()
            .await?;

        if !output.status.success() {
            bail!(
                "git {:?} failed: {}",
                args,
                String::from_utf8_lossy(&output.stderr).trim()
            );
        }
        Ok(String::from_utf8_lossy(&output.stdout).into_owned())
    }

    pub async fn create_branch(&self, name: &str) -> Result<()> {
        self.git(&["checkout", "-B", name]).await?;
        info!("Created and checked out branch: {}", name);
        Ok(())
    }

    pub async fn commit_experiment(&self, experiment: &Experiment) -> Result<String> {
        self.git(&["add", "-A"]).await?;

        let message = format!(
            "autoclaw: iteration {} - {}\n\nScore: {:.4}\nHypothesis: {}",
            experiment.iteration,
            if experiment
                .result
                .as_ref()
                .map(|r| r.passed)
                .unwrap_or(false)
            {
                "improvement"
            } else {
                "experiment"
            },
            experiment.result.as_ref().map(|r| r.score).unwrap_or(0.0),
            experiment.hypothesis
        );

        self.git(&["commit", "--allow-empty", "-m", &message])
            .await?;
        let hash = self.git(&["rev-parse", "HEAD"]).await?.trim().to_string();
        info!("Committed experiment: {}", &hash[..12.min(hash.len())]);
        Ok(hash)
    }

    pub async fn revert_last_changes(&self) -> Result<()> {
        // Discard uncommitted experiment changes and return to last commit.
        self.git(&["checkout", "--", "."]).await?;
        self.git(&["clean", "-fd"]).await?;
        debug!("Reverted working tree to HEAD");
        Ok(())
    }

    pub async fn get_experiment_history(&self) -> Result<Vec<ExperimentCommit>> {
        let log = self
            .git(&[
                "log",
                "--format=%H%x1f%s%x1f%at%x1f%an",
                "--grep=^autoclaw:",
            ])
            .await
            .unwrap_or_default();

        let commits = log
            .lines()
            .filter_map(|line| {
                let mut parts = line.split('\u{1f}');
                Some(ExperimentCommit {
                    hash: parts.next()?.to_string(),
                    message: parts.next()?.to_string(),
                    timestamp: parts.next()?.parse().ok()?,
                    author: parts.next().unwrap_or("").to_string(),
                })
            })
            .collect();

        Ok(commits)
    }

    pub async fn diff_with_parent(&self, commit_hash: &str) -> Result<String> {
        self.git(&["diff", &format!("{commit_hash}^"), commit_hash])
            .await
    }

    pub async fn list_branches(&self) -> Result<Vec<String>> {
        let out = self.git(&["branch", "--format=%(refname:short)"]).await?;
        Ok(out
            .lines()
            .map(str::trim)
            .filter(|b| b.starts_with("autoclaw-"))
            .map(String::from)
            .collect())
    }
}

#[derive(Debug, Clone)]
pub struct ExperimentCommit {
    pub hash: String,
    pub message: String,
    pub timestamp: i64,
    pub author: String,
}
