use crate::context::ContextEngine;
use crate::eval::{EvalEngine, EvalResult};
use crate::git::GitOps;
use crate::harness::ClaudeHarness;
use crate::metrics::MetricsCollector;
use crate::state::{RunState, StateManager};
use crate::triggers::{TriggerEngine, TriggerEvent};
use anyhow::Result;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{mpsc, RwLock};
use tokio::time::timeout;
use tracing::{debug, info, warn, error};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    pub context_path: String,
    pub budget_seconds: u64,
    pub headless: bool,
    pub max_iterations: usize,
    pub improvement_threshold: f64,
    pub auto_commit: bool,
    pub eval_rubric_path: String,
    pub workspace_path: String,
    pub claude_api_key: Option<String>,
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            context_path: "context.md".to_string(),
            budget_seconds: 300,
            headless: false,
            max_iterations: 1000,
            improvement_threshold: 0.01,
            auto_commit: true,
            eval_rubric_path: "eval_rubric.json".to_string(),
            workspace_path: ".autoclaw".to_string(),
            claude_api_key: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Experiment {
    pub id: String,
    pub iteration: usize,
    pub hypothesis: String,
    pub code_changes: Vec<CodeChange>,
    pub result: Option<EvalResult>,
    pub timestamp: chrono::DateTime<Utc>,
    pub duration_ms: u64,
    pub git_commit: Option<String>,
    pub parent_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeChange {
    pub file_path: String,
    pub diff: String,
    pub change_type: ChangeType,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChangeType {
    Add,
    Modify,
    Delete,
}

pub struct AgentLoop {
    config: AgentConfig,
    context: Arc<RwLock<ContextEngine>>,
    eval: Arc<EvalEngine>,
    git: Arc<GitOps>,
    harness: Arc<ClaudeHarness>,
    metrics: Arc<MetricsCollector>,
    state: Arc<StateManager>,
    triggers: Arc<TriggerEngine>,
    experiments: Arc<RwLock<Vec<Experiment>>>,
    best_result: Arc<RwLock<Option<EvalResult>>>,
    tx: mpsc::Sender<AgentEvent>,
    rx: Arc<RwLock<mpsc::Receiver<AgentEvent>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AgentEvent {
    ExperimentStarted(String),
    ExperimentCompleted(Experiment),
    ImprovementFound(Experiment),
    RegressionDetected(Experiment),
    TriggerActivated(TriggerEvent),
    Error(String),
}

impl AgentLoop {
    pub async fn new(config: AgentConfig) -> Result<Self> {
        let (tx, rx) = mpsc::channel(100);
        
        let context = Arc::new(RwLock::new(
            ContextEngine::new(&config.context_path).await?
        ));
        let eval = Arc::new(EvalEngine::new().await?);
        let git = Arc::new(GitOps::new(&config.workspace_path).await?);
        let harness = Arc::new(ClaudeHarness::new(
            config.claude_api_key.clone()
        ).await?);
        let metrics = Arc::new(MetricsCollector::new().await?);
        let state = Arc::new(StateManager::new(&config.workspace_path).await?);
        let triggers = Arc::new(TriggerEngine::new().await?);
        
        Ok(Self {
            config,
            context,
            eval,
            git,
            harness,
            metrics,
            state,
            triggers,
            experiments: Arc::new(RwLock::new(Vec::new())),
            best_result: Arc::new(RwLock::new(None)),
            tx,
            rx: Arc::new(RwLock::new(rx)),
        })
    }
    
    pub async fn run(&self) -> Result<()> {
        info!("Starting Autoclaw agent loop");
        
        // Initialize feature branch
        let branch_name = format!("autoclaw-{}", Uuid::new_v4().to_string()[..8].to_string());
        self.git.create_branch(&branch_name).await?;
        
        // Load previous state if exists
        let start_iteration = self.state.get_last_iteration().await.unwrap_or(0);
        
        for iteration in start_iteration..self.config.max_iterations {
            info!("Starting iteration {}", iteration);
            
            let experiment = self.run_experiment(iteration).await?;
            
            match experiment.result {
                Some(ref result) => {
                    let mut best = self.best_result.write().await;
                    
                    let is_improvement = match best.as_ref() {
                        None => true,
                        Some(b) => result.score > b.score + self.config.improvement_threshold,
                    };
                    
                    if is_improvement {
                        info!("Improvement found! Score: {}", result.score);
                        *best = Some(result.clone());
                        
                        if self.config.auto_commit {
                            let commit_hash = self.git.commit_experiment(&experiment).await?;
                            self.update_experiment_commit(&experiment.id, commit_hash).await?;
                        }
                        
                        self.tx.send(AgentEvent::ImprovementFound(experiment.clone())).await?;
                        
                        // Update context with learnings
                        self.update_context_with_learning(&experiment).await?;
                    } else {
                        self.tx.send(AgentEvent::RegressionDetected(experiment.clone())).await?;
                        // Revert changes
                        self.git.revert_last_changes().await?;
                    }
                }
                None => {
                    warn!("Experiment {} completed without result", experiment.id);
                }
            }
            
            self.state.save_iteration(iteration).await?;
            
            // Check triggers
            self.check_triggers().await?;
        }
        
        info!("Agent loop completed after {} iterations", self.config.max_iterations);
        Ok(())
    }
    
    async fn run_experiment(&self, iteration: usize) -> Result<Experiment> {
        let start = std::time::Instant::now();
        let experiment_id = Uuid::new_v4().to_string();
        
        self.tx.send(AgentEvent::ExperimentStarted(experiment_id.clone())).await?;
        
        // Get current context
        let context = self.context.read().await;
        let context_str = context.get_context().await?;
        drop(context);
        
        // Generate hypothesis via Claude
        let hypothesis = self.harness.generate_hypothesis(&context_str, iteration).await?;
        
        // Generate code changes
        let code_changes = self.harness.generate_changes(&context_str, &hypothesis).await?;
        
        // Apply changes
        self.apply_changes(&code_changes).await?;
        
        // Run evaluation with time budget
        let eval_result = timeout(
            Duration::from_secs(self.config.budget_seconds),
            self.eval.evaluate(&experiment_id)
        ).await;
        
        let result = match eval_result {
            Ok(Ok(r)) => Some(r),
            Ok(Err(e)) => {
                error!("Evaluation error: {}", e);
                None
            }
            Err(_) => {
                warn!("Evaluation timed out after {}s", self.config.budget_seconds);
                None
            }
        };
        
        let duration_ms = start.elapsed().as_millis() as u64;
        
        let experiment = Experiment {
            id: experiment_id,
            iteration,
            hypothesis,
            code_changes,
            result,
            timestamp: Utc::now(),
            duration_ms,
            git_commit: None,
            parent_id: self.get_parent_id().await,
        };
        
        self.experiments.write().await.push(experiment.clone());
        self.tx.send(AgentEvent::ExperimentCompleted(experiment.clone())).await?;
        
        Ok(experiment)
    }
    
    async fn apply_changes(&self, changes: &[CodeChange]) -> Result<()> {
        for change in changes {
            match change.change_type {
                ChangeType::Add | ChangeType::Modify => {
                    tokio::fs::write(&change.file_path, &change.diff).await?;
                }
                ChangeType::Delete => {
                    tokio::fs::remove_file(&change.file_path).await?;
                }
            }
        }
        Ok(())
    }
    
    async fn update_context_with_learning(&self, experiment: &Experiment) -> Result<()> {
        let mut context = self.context.write().await;
        
        let learning = format!(
            "\n## Learning {}\n- Hypothesis: {}\n- Result: {}\n- Score: {:.4}\n",
            experiment.iteration,
            experiment.hypothesis,
            experiment.result.as_ref().map(|r| format!("{:.4}", r.score)).unwrap_or("N/A".to_string()),
            experiment.result.as_ref().map(|r| r.score).unwrap_or(0.0)
        );
        
        context.append_learning(&learning).await?;
        Ok(())
    }
    
    async fn update_experiment_commit(&self, experiment_id: &str, commit_hash: String) -> Result<()> {
        let mut experiments = self.experiments.write().await;
        if let Some(exp) = experiments.iter_mut().find(|e| e.id == experiment_id) {
            exp.git_commit = Some(commit_hash);
        }
        Ok(())
    }
    
    async fn get_parent_id(&self) -> Option<String> {
        let experiments = self.experiments.read().await;
        experiments.last().map(|e| e.id.clone())
    }
    
    async fn check_triggers(&self) -> Result<()> {
        let triggers = self.triggers.check_all().await?;
        for trigger in triggers {
            self.tx.send(AgentEvent::TriggerActivated(trigger)).await?;
        }
        Ok(())
    }
    
    pub async fn get_experiments(&self) -> Vec<Experiment> {
        self.experiments.read().await.clone()
    }
    
    pub async fn get_best_result(&self) -> Option<EvalResult> {
        self.best_result.read().await.clone()
    }
    
    pub fn subscribe(&self) -> mpsc::Receiver<AgentEvent> {
        let (tx, rx) = mpsc::channel(100);
        // Clone sender for event distribution
        rx
    }
}
