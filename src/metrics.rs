//! In-process metrics with hand-rendered Prometheus text output.
//!
//! No global recorder, no exporter crates: the snapshot struct is the
//! single source of truth and renders itself in Prometheus exposition
//! format on demand.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info};

pub struct MetricsCollector {
    storage: Arc<RwLock<MetricsStorage>>,
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
        info!("Metrics collector initialized");
        Ok(Self {
            storage: Arc::new(RwLock::new(MetricsStorage::default())),
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

        if storage
            .best_score
            .map(|s| metrics.score > s)
            .unwrap_or(true)
        {
            storage.best_score = Some(metrics.score);
        }

        storage.current_iteration = metrics.iteration;

        debug!(
            "Recorded experiment {}: score={:.4}, duration={}ms",
            metrics.iteration, metrics.score, metrics.duration_ms
        );

        Ok(())
    }

    pub async fn record_custom(&self, name: &str, value: f64) -> Result<()> {
        self.storage
            .write()
            .await
            .custom_metrics
            .insert(name.to_string(), value);
        Ok(())
    }

    pub async fn get_snapshot(&self) -> MetricsStorage {
        self.storage.read().await.clone()
    }

    pub async fn get_prometheus_output(&self) -> String {
        let s = self.storage.read().await;
        let mut out = String::new();

        out.push_str("# TYPE autoclaw_experiments_total counter\n");
        out.push_str(&format!(
            "autoclaw_experiments_total {}\n",
            s.experiments_total
        ));
        out.push_str("# TYPE autoclaw_experiments_successful counter\n");
        out.push_str(&format!(
            "autoclaw_experiments_successful {}\n",
            s.experiments_successful
        ));
        out.push_str("# TYPE autoclaw_experiments_failed counter\n");
        out.push_str(&format!(
            "autoclaw_experiments_failed {}\n",
            s.experiments_failed
        ));
        out.push_str("# TYPE autoclaw_current_iteration gauge\n");
        out.push_str(&format!(
            "autoclaw_current_iteration {}\n",
            s.current_iteration
        ));
        if let Some(best) = s.best_score {
            out.push_str("# TYPE autoclaw_best_score gauge\n");
            out.push_str(&format!("autoclaw_best_score {best}\n"));
        }
        for (name, value) in &s.custom_metrics {
            let safe: String = name
                .chars()
                .map(|c| {
                    if c.is_ascii_alphanumeric() || c == '_' {
                        c
                    } else {
                        '_'
                    }
                })
                .collect();
            out.push_str(&format!("autoclaw_custom_{safe} {value}\n"));
        }

        out
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
        *self.storage.write().await = loaded;
        info!("Loaded metrics from {}", path);
        Ok(())
    }
}
