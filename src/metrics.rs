use anyhow::Result;
use metrics::{counter, gauge, histogram};
use metrics_exporter_prometheus::PrometheusBuilder;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info};

pub struct MetricsCollector {
    storage: Arc<RwLock<MetricsStorage>>,
    prometheus_handle: Option<metrics_exporter_prometheus::PrometheusHandle>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MetricsStorage {
    pub experiments_total: u64,
    pub experiments_successful: u64,
    pub experiments_failed: u64,
    pub best_score: Option<f64>,
    pub current_iteration: usize,
    pub runtime_seconds: u64,
    pub custom_metrics: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExperimentMetrics {
    pub iteration: usize,
    pub duration_ms: u64,
    pub score: f64,
    pub passed: bool,
    pub tokens_used: u64,
    pub code_changes: usize,
}

impl MetricsCollector {
    pub async fn new() -> Result<Self> {
        let storage = Arc::new(RwLock::new(MetricsStorage::default()));
        
        // Setup Prometheus exporter
        let builder = PrometheusBuilder::new();
        let handle = builder.install_recorder()?;
        
        info!("Metrics collector initialized");
        
        Ok(Self {
            storage,
            prometheus_handle: Some(handle),
        })
    }
    
    pub async fn record_experiment(&self, metrics: ExperimentMetrics) -> Result<()> {
        let mut storage = self.storage.write().await;
        
        storage.experiments_total += 1;
        if metrics.passed {
            storage.experiments_successful += 1;
        } else {
            storage.experiments_failed += 1;
        }
        
        if storage.best_score.map(|s| metrics.score > s).unwrap_or(true) {
            storage.best_score = Some(metrics.score);
        }
        
        storage.current_iteration = metrics.iteration;
        
        drop(storage);
        
        // Record to Prometheus
        counter!("autoclaw_experiments_total", 1);
        if metrics.passed {
            counter!("autoclaw_experiments_successful", 1);
        } else {
            counter!("autoclaw_experiments_failed", 1);
        }
        
        gauge!("autoclaw_current_iteration", metrics.iteration as f64);
        gauge!("autoclaw_experiment_score", metrics.score);
        histogram!("autoclaw_experiment_duration_ms", metrics.duration_ms as f64);
        
        debug!(
            "Recorded experiment {}: score={:.4}, duration={}ms",
            metrics.iteration, metrics.score, metrics.duration_ms
        );
        
        Ok(())
    }
    
    pub async fn record_custom(&self, name: &str, value: f64) -> Result<()> {
        let mut storage = self.storage.write().await;
        storage.custom_metrics.insert(name.to_string(), value);
        drop(storage);
        
        gauge!(format!("autoclaw_custom_{}", name), value);
        Ok(())
    }
    
    pub async fn get_snapshot(&self) -> MetricsStorage {
        self.storage.read().await.clone()
    }
    
    pub fn get_prometheus_output(&self) -> Option<String> {
        self.prometheus_handle.as_ref().map(|h| h.render())
    }
    
    pub async fn save_to_file(&self, path: &str) -> Result<()> {
        let storage = self.storage.read().await;
        let json = serde_json::to_string_pretty(&*storage)?;
        tokio::fs::write(path, json).await?;
        Ok(())
    }
    
    pub async fn load_from_file(&self, path: &str) -> Result<()> {
        let content = tokio::fs::read_to_string(path).await?;
        let loaded: MetricsStorage = serde_json::from_str(&content)?;
        
        let mut storage = self.storage.write().await;
        *storage = loaded;
        
        info!("Loaded metrics from {}", path);
        Ok(())
    }
    
    pub async fn get_adoption_metrics(&self) -> AdoptionMetrics {
        let storage = self.storage.read().await;
        
        AdoptionMetrics {
            activation_rate: self.calculate_activation_rate(&storage),
            day1_retention: 0.55, // Placeholder - would come from user tracking
            day7_retention: 0.35,
            day30_retention: 0.20,
            feature_adoption: 0.70,
        }
    }
    
    fn calculate_activation_rate(&self, storage: &MetricsStorage) -> f64 {
        if storage.experiments_total == 0 {
            0.0
        } else {
            storage.experiments_successful as f64 / storage.experiments_total as f64
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdoptionMetrics {
    pub activation_rate: f64,
    pub day1_retention: f64,
    pub day7_retention: f64,
    pub day30_retention: f64,
    pub feature_adoption: f64,
}

impl AdoptionMetrics {
    pub fn to_innovation_format(&self) -> String {
        format!(
            r#"ADOPTION METRICS
- Activation Rate: {:.1}%
- Day-1 Retention: {:.1}%
- Day-7 Retention: {:.1}%
- Day-30 Retention: {:.1}%
- Feature Adoption: {:.1}%
"#,
            self.activation_rate * 100.0,
            self.day1_retention * 100.0,
            self.day7_retention * 100.0,
            self.day30_retention * 100.0,
            self.feature_adoption * 100.0
        )
    }
}
