use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tokio::fs;
use tracing::{debug, info};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunState {
    pub last_iteration: usize,
    pub best_experiment_id: Option<String>,
    pub best_score: Option<f64>,
    pub total_runtime_seconds: u64,
    pub current_branch: Option<String>,
    pub metadata: serde_json::Value,
}

impl Default for RunState {
    fn default() -> Self {
        Self {
            last_iteration: 0,
            best_experiment_id: None,
            best_score: None,
            total_runtime_seconds: 0,
            current_branch: None,
            metadata: serde_json::Value::Object(serde_json::Map::new()),
        }
    }
}

pub struct StateManager {
    workspace: PathBuf,
    state_file: PathBuf,
    cache: tokio::sync::RwLock<Option<RunState>>,
}

impl StateManager {
    pub async fn new(workspace: &str) -> Result<Self> {
        let workspace = PathBuf::from(workspace);
        let state_file = workspace.join("state.json");
        
        fs::create_dir_all(&workspace).await?;
        
        Ok(Self {
            workspace,
            state_file,
            cache: tokio::sync::RwLock::new(None),
        })
    }
    
    pub async fn load(&self) -> Result<RunState> {
        // Check cache first
        let cache = self.cache.read().await;
        if let Some(state) = cache.clone() {
            return Ok(state);
        }
        drop(cache);
        
        // Load from disk
        if self.state_file.exists() {
            let content = fs::read_to_string(&self.state_file).await?;
            let state: RunState = serde_json::from_str(&content)?;
            
            let mut cache = self.cache.write().await;
            *cache = Some(state.clone());
            
            info!("Loaded state from {:?}", self.state_file);
            Ok(state)
        } else {
            Ok(RunState::default())
        }
    }
    
    pub async fn save(&self, state: &RunState) -> Result<()> {
        let content = serde_json::to_string_pretty(state)?;
        fs::write(&self.state_file, content).await?;
        
        let mut cache = self.cache.write().await;
        *cache = Some(state.clone());
        
        debug!("Saved state to {:?}", self.state_file);
        Ok(())
    }
    
    pub async fn get_last_iteration(&self) -> Result<usize> {
        let state = self.load().await?;
        Ok(state.last_iteration)
    }
    
    pub async fn save_iteration(&self, iteration: usize) -> Result<()> {
        let mut state = self.load().await?;
        state.last_iteration = iteration;
        self.save(&state).await
    }
    
    pub async fn update_best(&self, experiment_id: &str, score: f64) -> Result<()> {
        let mut state = self.load().await?;
        state.best_experiment_id = Some(experiment_id.to_string());
        state.best_score = Some(score);
        self.save(&state).await
    }
    
    pub async fn set_branch(&self, branch: &str) -> Result<()> {
        let mut state = self.load().await?;
        state.current_branch = Some(branch.to_string());
        self.save(&state).await
    }
    
    pub async fn reset(&self) -> Result<()> {
        let state = RunState::default();
        self.save(&state).await?;
        
        if self.state_file.exists() {
            fs::remove_file(&self.state_file).await?;
        }
        
        info!("State reset");
        Ok(())
    }
}
