use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;
use tokio::sync::RwLock;
use tracing::{debug, info};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextSection {
    pub name: String,
    pub content: String,
    pub priority: u8,
    pub mutable: bool,
}

pub struct ContextEngine {
    path: PathBuf,
    sections: RwLock<HashMap<String, ContextSection>>,
    learnings: RwLock<Vec<String>>,
    metadata: RwLock<ContextMetadata>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ContextMetadata {
    pub version: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub last_modified: chrono::DateTime<chrono::Utc>,
    pub total_experiments: usize,
    pub best_score: Option<f64>,
}

impl ContextEngine {
    pub async fn new(path: &str) -> Result<Self> {
        let path = PathBuf::from(path);

        let engine = Self {
            path: path.clone(),
            sections: RwLock::new(HashMap::new()),
            learnings: RwLock::new(Vec::new()),
            metadata: RwLock::new(ContextMetadata::default()),
        };

        if path.exists() {
            engine.load().await?;
        } else {
            engine.create_default().await?;
        }

        Ok(engine)
    }

    async fn create_default(&self) -> Result<()> {
        let default_context = r#"# AUTOCALW CONTEXT

## MISSION
Build self-improving automation. Human edits this file. AI edits code. Loop forever.

## CONSTRAINTS
- Time budget: 300s per experiment
- Metric: lower validation loss = better
- Single file target: train.py
- Git branch: autoclaw-*

## CURRENT STATE
- Best score: N/A
- Iterations: 0
- Last hypothesis: N/A

## HYPOTHESIS QUEUE
1. Increase learning rate for faster convergence
2. Add dropout for regularization
3. Tune batch size for memory efficiency

## LEARNINGS
<!-- AI appends here -->

## TOOLS
- File read/write
- Shell exec
- Git ops
- Metrics collect
"#;

        fs::write(&self.path, default_context).await?;
        self.parse_sections(default_context).await?;

        info!("Created default context at {:?}", self.path);
        Ok(())
    }

    async fn load(&self) -> Result<()> {
        let content = fs::read_to_string(&self.path).await?;
        self.parse_sections(&content).await?;
        debug!("Loaded context from {:?}", self.path);
        Ok(())
    }

    async fn parse_sections(&self, content: &str) -> Result<()> {
        let mut sections = self.sections.write().await;
        sections.clear();

        let mut current_name = String::new();
        let mut current_content = String::new();

        for line in content.lines() {
            if let Some(heading) = line.strip_prefix("## ") {
                if !current_name.is_empty() {
                    sections.insert(
                        current_name.clone(),
                        ContextSection {
                            name: current_name.clone(),
                            content: current_content.trim().to_string(),
                            priority: self.infer_priority(&current_name),
                            mutable: self.infer_mutability(&current_name),
                        },
                    );
                }
                current_name = heading.trim().to_string();
                current_content = String::new();
            } else {
                current_content.push_str(line);
                current_content.push('\n');
            }
        }

        if !current_name.is_empty() {
            sections.insert(
                current_name.clone(),
                ContextSection {
                    name: current_name,
                    content: current_content.trim().to_string(),
                    priority: 5,
                    mutable: true,
                },
            );
        }

        Ok(())
    }

    fn infer_priority(&self, name: &str) -> u8 {
        match name.to_uppercase().as_str() {
            "MISSION" => 1,
            "CONSTRAINTS" => 2,
            "CURRENT STATE" => 3,
            "HYPOTHESIS QUEUE" => 4,
            "LEARNINGS" => 5,
            "TOOLS" => 6,
            _ => 5,
        }
    }

    fn infer_mutability(&self, name: &str) -> bool {
        !matches!(name.to_uppercase().as_str(), "MISSION" | "CONSTRAINTS")
    }

    pub async fn get_context(&self) -> Result<String> {
        let sections = self.sections.read().await;
        let mut ordered: Vec<_> = sections.values().collect();
        ordered.sort_by_key(|s| s.priority);

        let mut result = String::new();
        for section in ordered {
            result.push_str(&format!("## {}\n{}\n\n", section.name, section.content));
        }

        Ok(result)
    }

    pub async fn get_section(&self, name: &str) -> Result<Option<String>> {
        let sections = self.sections.read().await;
        Ok(sections.get(name).map(|s| s.content.clone()))
    }

    pub async fn update_section(&self, name: &str, content: &str) -> Result<()> {
        let mut sections = self.sections.write().await;

        if let Some(section) = sections.get_mut(name) {
            if !section.mutable {
                anyhow::bail!("Section '{}' is immutable", name);
            }
            section.content = content.to_string();
        } else {
            sections.insert(
                name.to_string(),
                ContextSection {
                    name: name.to_string(),
                    content: content.to_string(),
                    priority: 5,
                    mutable: true,
                },
            );
        }

        drop(sections);
        self.save().await?;
        Ok(())
    }

    pub async fn append_learning(&self, learning: &str) -> Result<()> {
        let mut learnings = self.learnings.write().await;
        learnings.push(learning.to_string());

        // Also update the LEARNINGS section
        let all_learnings = learnings.join("\n");
        drop(learnings);

        self.update_section("LEARNINGS", &all_learnings).await?;
        Ok(())
    }

    pub async fn update_best_score(&self, score: f64) -> Result<()> {
        let mut metadata = self.metadata.write().await;
        metadata.best_score = Some(score);
        metadata.total_experiments += 1;
        metadata.last_modified = chrono::Utc::now();
        drop(metadata);

        self.update_section(
            "CURRENT STATE",
            &format!(
                "- Best score: {:.4}\n- Iterations: {}\n- Last updated: {}",
                score,
                self.metadata.read().await.total_experiments,
                chrono::Utc::now().to_rfc3339()
            ),
        )
        .await?;

        Ok(())
    }

    async fn save(&self) -> Result<()> {
        let content = self.get_context().await?;
        fs::write(&self.path, content).await?;
        debug!("Saved context to {:?}", self.path);
        Ok(())
    }

    pub async fn get_token_estimate(&self) -> usize {
        let context = self.get_context().await.unwrap_or_default();
        // Rough estimate: 4 chars ~ 1 token
        context.len() / 4
    }

    pub async fn compress_if_needed(&self, max_tokens: usize) -> Result<String> {
        let current_tokens = self.get_token_estimate().await;

        if current_tokens <= max_tokens {
            return self.get_context().await;
        }

        // Compress by summarizing old learnings
        let mut sections = self.sections.write().await;

        if let Some(learnings) = sections.get_mut("LEARNINGS") {
            let lines: Vec<_> = learnings.content.lines().collect();
            if lines.len() > 10 {
                let summary = format!(
                    "[{} older learnings summarized]\n{}",
                    lines.len() - 5,
                    lines[lines.len() - 5..].join("\n")
                );
                learnings.content = summary;
            }
        }

        drop(sections);
        self.save().await?;
        self.get_context().await
    }
}
