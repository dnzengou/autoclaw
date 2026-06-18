use anyhow::{Result, Context as _};
use git2::{Repository, Signature, Oid};
use std::path::PathBuf;
use tracing::{debug, info, warn};
use crate::agent::Experiment;

pub struct GitOps {
    repo: Repository,
    workspace: PathBuf,
}

impl GitOps {
    pub async fn new(workspace: &str) -> Result<Self> {
        let workspace = PathBuf::from(workspace);
        
        // Ensure workspace exists
        tokio::fs::create_dir_all(&workspace).await?;
        
        // Open or init repo
        let repo = match Repository::open(&workspace) {
            Ok(repo) => repo,
            Err(_) => {
                info!("Initializing new git repository");
                Repository::init(&workspace)?
            }
        };
        
        Ok(Self { repo, workspace })
    }
    
    pub async fn create_branch(&self, name: &str) -> Result<()> {
        let head = self.repo.head()?;
        let head_commit = head.peel_to_commit()?;
        
        // Create branch
        self.repo.branch(name, &head_commit, false)?;
        
        // Checkout branch
        let tree = head_commit.tree()?;
        self.repo.checkout_tree(tree.as_object(), None)?;
        
        info!("Created and checked out branch: {}", name);
        Ok(())
    }
    
    pub async fn commit_experiment(&self, experiment: &Experiment) -> Result<String> {
        let mut index = self.repo.index()?;
        
        // Add all changes
        index.add_all(["*"].iter(), git2::IndexAddOption::DEFAULT, None)?;
        index.write()?;
        
        let tree_id = index.write_tree()?;
        let tree = self.repo.find_tree(tree_id)?;
        
        let parent_commit = self.repo.head()?.peel_to_commit()?;
        
        let signature = Signature::now("Autoclaw", "autoclaw@localhost")?;
        
        let message = format!(
            "autoclaw: iteration {} - {}\n\nScore: {:.4}\nHypothesis: {}",
            experiment.iteration,
            if experiment.result.as_ref().map(|r| r.passed).unwrap_or(false) {
                "improvement"
            } else {
                "experiment"
            },
            experiment.result.as_ref().map(|r| r.score).unwrap_or(0.0),
            experiment.hypothesis
        );
        
        let commit_id = self.repo.commit(
            Some("HEAD"),
            &signature,
            &signature,
            &message,
            &tree,
            &[&parent_commit],
        )?;
        
        let commit_hash = commit_id.to_string();
        info!("Committed experiment: {}", &commit_hash[..12]);
        
        Ok(commit_hash)
    }
    
    pub async fn revert_last_changes(&self) -> Result<()> {
        let head = self.repo.head()?;
        let head_commit = head.peel_to_commit()?;
        
        // Reset to parent commit
        if let Some(parent) = head_commit.parent(0) {
            let parent_tree = parent.tree()?;
            self.repo.checkout_tree(
                parent_tree.as_object(),
                Some(git2::build::CheckoutBuilder::new().force()),
            )?;
            
            // Move HEAD to parent
            self.repo.set_head_detached(parent.id())?;
            
            debug!("Reverted to parent commit");
        }
        
        Ok(())
    }
    
    pub async fn get_experiment_history(&self) -> Result<Vec<ExperimentCommit>> {
        let mut commits = Vec::new();
        let mut revwalk = self.repo.revwalk()?;
        revwalk.push_head()?;
        
        for oid in revwalk {
            let oid = oid?;
            let commit = self.repo.find_commit(oid)?;
            let message = commit.message().unwrap_or("");
            
            if message.starts_with("autoclaw:") {
                commits.push(ExperimentCommit {
                    hash: oid.to_string(),
                    message: message.to_string(),
                    timestamp: commit.time().seconds(),
                    author: commit.author().name().unwrap_or("").to_string(),
                });
            }
        }
        
        Ok(commits)
    }
    
    pub async fn diff_with_parent(&self, commit_hash: &str) -> Result<String> {
        let oid = Oid::from_str(commit_hash)?;
        let commit = self.repo.find_commit(oid)?;
        let tree = commit.tree()?;
        
        let parent = commit.parent(0)?;
        let parent_tree = parent.tree()?;
        
        let diff = self.repo.diff_tree_to_tree(
            Some(&parent_tree),
            Some(&tree),
            None,
        )?;
        
        let mut diff_str = String::new();
        diff.print(git2::DiffFormat::Patch, |_, _, line| {
            diff_str.push_str(std::str::from_utf8(line.content()).unwrap_or(""));
            true
        })?;
        
        Ok(diff_str)
    }
    
    pub async fn stash_changes(&self, message: &str) -> Result<()> {
        let signature = Signature::now("Autoclaw", "autoclaw@localhost")?;
        self.repo.stash_save(&signature, message, None)?;
        Ok(())
    }
    
    pub async fn list_branches(&self) -> Result<Vec<String>> {
        let branches = self.repo.branches(None)?;
        let mut result = Vec::new();
        
        for branch in branches {
            let (branch, _) = branch?;
            if let Some(name) = branch.name()? {
                if name.starts_with("autoclaw-") {
                    result.push(name.to_string());
                }
            }
        }
        
        Ok(result)
    }
    
    pub async fn merge_branch(&self, branch_name: &str) -> Result<()> {
        let branch = self.repo.find_branch(branch_name, git2::BranchType::Local)?;
        let branch_ref = branch.get().peel_to_commit()?;
        
        let head = self.repo.head()?.peel_to_commit()?;
        
        // Simple fast-forward merge
        self.repo.checkout_tree(
            branch_ref.tree()?.as_object(),
            Some(git2::build::CheckoutBuilder::new().force()),
        )?;
        
        self.repo.set_head_detached(branch_ref.id())?;
        
        info!("Merged branch: {}", branch_name);
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct ExperimentCommit {
    pub hash: String,
    pub message: String,
    pub timestamp: i64,
    pub author: String,
}
