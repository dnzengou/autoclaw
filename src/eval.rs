use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;
use tracing::{debug, info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalResult {
    pub run_id: String,
    pub score: f64,
    pub metrics: HashMap<String, f64>,
    pub rubric_scores: HashMap<String, f64>,
    pub passed: bool,
    pub duration_ms: u64,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalRubric {
    pub name: String,
    pub version: String,
    pub criteria: Vec<EvalCriterion>,
    pub weights: HashMap<String, f64>,
    pub thresholds: Thresholds,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalCriterion {
    pub id: String,
    pub name: String,
    pub description: String,
    pub metric_type: MetricType,
    pub target: f64,
    pub weight: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MetricType {
    LowerIsBetter,
    HigherIsBetter,
    ExactMatch,
    Range { min: f64, max: f64 },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thresholds {
    pub excellent: f64,
    pub good: f64,
    pub acceptable: f64,
    pub poor: f64,
}

pub struct EvalEngine {
    rubric: EvalRubric,
    custom_evaluators: HashMap<String, Box<dyn Evaluator + Send + Sync>>,
}

#[async_trait::async_trait]
pub trait Evaluator {
    async fn evaluate(&self, run_id: &str) -> Result<f64>;
    fn name(&self) -> &str;
}

impl EvalEngine {
    pub async fn new() -> Result<Self> {
        let rubric = Self::load_default_rubric().await?;
        
        Ok(Self {
            rubric,
            custom_evaluators: HashMap::new(),
        })
    }
    
    pub async fn with_rubric(path: &str) -> Result<Self> {
        let content = fs::read_to_string(path).await?;
        let rubric: EvalRubric = serde_json::from_str(&content)?;
        
        info!("Loaded custom rubric: {} v{}", rubric.name, rubric.version);
        
        Ok(Self {
            rubric,
            custom_evaluators: HashMap::new(),
        })
    }
    
    async fn load_default_rubric() -> Result<EvalRubric> {
        Ok(EvalRubric {
            name: "Autoclaw Default".to_string(),
            version: "1.0.0".to_string(),
            criteria: vec![
                EvalCriterion {
                    id: "validation_loss".to_string(),
                    name: "Validation Loss".to_string(),
                    description: "Bits per byte on validation set".to_string(),
                    metric_type: MetricType::LowerIsBetter,
                    target: 2.0,
                    weight: 0.4,
                },
                EvalCriterion {
                    id: "training_speed".to_string(),
                    name: "Training Speed".to_string(),
                    description: "Tokens processed per second".to_string(),
                    metric_type: MetricType::HigherIsBetter,
                    target: 10000.0,
                    weight: 0.2,
                },
                EvalCriterion {
                    id: "memory_efficiency".to_string(),
                    name: "Memory Efficiency".to_string(),
                    description: "GPU memory utilization ratio".to_string(),
                    metric_type: MetricType::Range { min: 0.7, max: 0.95 },
                    target: 0.85,
                    weight: 0.2,
                },
                EvalCriterion {
                    id: "code_quality".to_string(),
                    name: "Code Quality".to_string(),
                    description: "Static analysis score".to_string(),
                    metric_type: MetricType::HigherIsBetter,
                    target: 0.9,
                    weight: 0.2,
                },
            ],
            weights: [
                ("validation_loss".to_string(), 0.4),
                ("training_speed".to_string(), 0.2),
                ("memory_efficiency".to_string(), 0.2),
                ("code_quality".to_string(), 0.2),
            ].into_iter().collect(),
            thresholds: Thresholds {
                excellent: 0.9,
                good: 0.75,
                acceptable: 0.6,
                poor: 0.4,
            },
        })
    }
    
    pub async fn evaluate(&self, run_id: &str) -> Result<EvalResult> {
        let start = std::time::Instant::now();
        
        // Collect metrics
        let metrics = self.collect_metrics(run_id).await?;
        
        // Score each criterion
        let mut rubric_scores = HashMap::new();
        let mut total_score = 0.0;
        let mut total_weight = 0.0;
        
        for criterion in &self.rubric.criteria {
            if let Some(metric_value) = metrics.get(&criterion.id) {
                let score = self.score_criterion(criterion, *metric_value);
                rubric_scores.insert(criterion.id.clone(), score);
                total_score += score * criterion.weight;
                total_weight += criterion.weight;
            }
        }
        
        let final_score = if total_weight > 0.0 {
            total_score / total_weight
        } else {
            0.0
        };
        
        let passed = final_score >= self.rubric.thresholds.acceptable;
        
        Ok(EvalResult {
            run_id: run_id.to_string(),
            score: final_score,
            metrics,
            rubric_scores,
            passed,
            duration_ms: start.elapsed().as_millis() as u64,
            timestamp: chrono::Utc::now(),
        })
    }
    
    async fn collect_metrics(&self, run_id: &str) -> Result<HashMap<String, f64>> {
        let mut metrics = HashMap::new();
        
        // Read from metrics file if exists
        let metrics_path = format!(".autoclaw/metrics/{}.json", run_id);
        if PathBuf::from(&metrics_path).exists() {
            let content = fs::read_to_string(&metrics_path).await?;
            let file_metrics: HashMap<String, f64> = serde_json::from_str(&content)?;
            metrics.extend(file_metrics);
        }
        
        // Run custom evaluators
        for (name, evaluator) in &self.custom_evaluators {
            match evaluator.evaluate(run_id).await {
                Ok(score) => {
                    metrics.insert(name.clone(), score);
                }
                Err(e) => {
                    warn!("Evaluator {} failed: {}", name, e);
                }
            }
        }
        
        Ok(metrics)
    }
    
    fn score_criterion(&self, criterion: &EvalCriterion, value: f64) -> f64 {
        match &criterion.metric_type {
            MetricType::LowerIsBetter => {
                if value <= criterion.target {
                    1.0
                } else {
                    let ratio = criterion.target / value;
                    ratio.clamp(0.0, 1.0)
                }
            }
            MetricType::HigherIsBetter => {
                if value >= criterion.target {
                    1.0
                } else {
                    let ratio = value / criterion.target;
                    ratio.clamp(0.0, 1.0)
                }
            }
            MetricType::ExactMatch => {
                if (value - criterion.target).abs() < f64::EPSILON {
                    1.0
                } else {
                    0.0
                }
            }
            MetricType::Range { min, max } => {
                if value >= *min && value <= *max {
                    1.0
                } else if value < *min {
                    (value / min).clamp(0.0, 1.0)
                } else {
                    (max / value).clamp(0.0, 1.0)
                }
            }
        }
    }
    
    pub fn classify_score(&self, score: f64) -> ScoreClass {
        if score >= self.rubric.thresholds.excellent {
            ScoreClass::Excellent
        } else if score >= self.rubric.thresholds.good {
            ScoreClass::Good
        } else if score >= self.rubric.thresholds.acceptable {
            ScoreClass::Acceptable
        } else {
            ScoreClass::Poor
        }
    }
    
    pub fn register_evaluator(&mut self, name: &str, evaluator: Box<dyn Evaluator + Send + Sync>) {
        self.custom_evaluators.insert(name.to_string(), evaluator);
    }
    
    pub fn get_rubric(&self) -> &EvalRubric {
        &self.rubric
    }
    
    pub async fn save_rubric(&self, path: &str) -> Result<()> {
        let content = serde_json::to_string_pretty(&self.rubric)?;
        fs::write(path, content).await?;
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScoreClass {
    Excellent,
    Good,
    Acceptable,
    Poor,
}

impl ScoreClass {
    pub fn as_str(&self) -> &'static str {
        match self {
            ScoreClass::Excellent => "excellent",
            ScoreClass::Good => "good",
            ScoreClass::Acceptable => "acceptable",
            ScoreClass::Poor => "poor",
        }
    }
}

// Built-in evaluators

pub struct ValidationLossEvaluator;

#[async_trait::async_trait]
impl Evaluator for ValidationLossEvaluator {
    async fn evaluate(&self, run_id: &str) -> Result<f64> {
        let log_path = format!(".autoclaw/logs/{}.log", run_id);
        let content = fs::read_to_string(&log_path).await?;
        
        // Parse validation loss from log
        for line in content.lines().rev() {
            if line.contains("val_bpb") {
                if let Some(idx) = line.find("val_bpb:") {
                    let value_str = &line[idx + 8..].trim();
                    if let Ok(value) = value_str.parse::<f64>() {
                        return Ok(value);
                    }
                }
            }
        }
        
        anyhow::bail!("Could not find validation loss in log")
    }
    
    fn name(&self) -> &str {
        "validation_loss"
    }
}
