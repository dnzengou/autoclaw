use anyhow::Result;
use serde::{Deserialize, Serialize};
use tracing::{debug, info};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerEvent {
    pub id: String,
    pub trigger_type: TriggerType,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub data: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TriggerType {
    ScoreThreshold {
        threshold: f64,
        comparison: Comparison,
    },
    TimeElapsed {
        seconds: u64,
    },
    IterationCount {
        count: usize,
    },
    NoImprovement {
        iterations: usize,
    },
    Custom {
        name: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Comparison {
    GreaterThan,
    LessThan,
    Equal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trigger {
    pub id: String,
    pub trigger_type: TriggerType,
    pub enabled: bool,
    pub actions: Vec<TriggerAction>,
    pub cooldown_seconds: u64,
    pub last_triggered: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TriggerAction {
    Notify,
    StopAgent,
    SaveCheckpoint,
    UpdateContext { section: String, content: String },
    ExecuteCommand { command: String },
    Webhook { url: String },
}

pub struct TriggerEngine {
    triggers: tokio::sync::RwLock<Vec<Trigger>>,
    state: tokio::sync::RwLock<TriggerState>,
}

#[derive(Debug, Clone, Default)]
struct TriggerState {
    iteration_count: usize,
    last_improvement_iteration: usize,
    best_score: Option<f64>,
    start_time: Option<chrono::DateTime<chrono::Utc>>,
}

impl TriggerEngine {
    pub async fn new() -> Result<Self> {
        let engine = Self {
            triggers: tokio::sync::RwLock::new(Self::default_triggers()),
            state: tokio::sync::RwLock::new(TriggerState {
                start_time: Some(chrono::Utc::now()),
                ..Default::default()
            }),
        };

        info!(
            "Trigger engine initialized with {} default triggers",
            engine.triggers.read().await.len()
        );

        Ok(engine)
    }

    fn default_triggers() -> Vec<Trigger> {
        vec![
            Trigger {
                id: "excellent_score".to_string(),
                trigger_type: TriggerType::ScoreThreshold {
                    threshold: 0.9,
                    comparison: Comparison::GreaterThan,
                },
                enabled: true,
                actions: vec![TriggerAction::Notify, TriggerAction::SaveCheckpoint],
                cooldown_seconds: 3600,
                last_triggered: None,
            },
            Trigger {
                id: "no_improvement_50".to_string(),
                trigger_type: TriggerType::NoImprovement { iterations: 50 },
                enabled: true,
                actions: vec![
                    TriggerAction::Notify,
                    TriggerAction::UpdateContext {
                        section: "HYPOTHESIS QUEUE".to_string(),
                        content:
                            "Try radical architecture changes - no improvement in 50 iterations"
                                .to_string(),
                    },
                ],
                cooldown_seconds: 0,
                last_triggered: None,
            },
            Trigger {
                id: "checkpoint_hourly".to_string(),
                trigger_type: TriggerType::TimeElapsed { seconds: 3600 },
                enabled: true,
                actions: vec![TriggerAction::SaveCheckpoint],
                cooldown_seconds: 3600,
                last_triggered: None,
            },
        ]
    }

    pub async fn check_all(&self) -> Result<Vec<TriggerEvent>> {
        let triggers = self.triggers.read().await;
        let state = self.state.read().await;
        let mut events = Vec::new();

        for trigger in triggers.iter().filter(|t| t.enabled) {
            if let Some(event) = self.check_trigger(trigger, &state).await {
                events.push(event);
            }
        }

        Ok(events)
    }

    async fn check_trigger(&self, trigger: &Trigger, state: &TriggerState) -> Option<TriggerEvent> {
        // Check cooldown
        if let Some(last) = trigger.last_triggered {
            let elapsed = chrono::Utc::now().signed_duration_since(last);
            if elapsed.num_seconds() < trigger.cooldown_seconds as i64 {
                return None;
            }
        }

        let should_trigger = match &trigger.trigger_type {
            TriggerType::ScoreThreshold {
                threshold,
                comparison,
            } => state
                .best_score
                .map(|score| match comparison {
                    Comparison::GreaterThan => score > *threshold,
                    Comparison::LessThan => score < *threshold,
                    Comparison::Equal => (score - threshold).abs() < f64::EPSILON,
                })
                .unwrap_or(false),
            TriggerType::TimeElapsed { seconds } => state
                .start_time
                .map(|start| {
                    let elapsed = chrono::Utc::now().signed_duration_since(start);
                    elapsed.num_seconds() >= *seconds as i64
                })
                .unwrap_or(false),
            TriggerType::IterationCount { count } => state.iteration_count >= *count,
            TriggerType::NoImprovement { iterations } => {
                state.iteration_count - state.last_improvement_iteration >= *iterations
            }
            TriggerType::Custom { name } => {
                debug!("Checking custom trigger: {}", name);
                false
            }
        };

        if should_trigger {
            Some(TriggerEvent {
                id: trigger.id.clone(),
                trigger_type: trigger.trigger_type.clone(),
                timestamp: chrono::Utc::now(),
                data: serde_json::json!({
                    "iteration": state.iteration_count,
                    "best_score": state.best_score,
                }),
            })
        } else {
            None
        }
    }

    pub async fn update_state(&self, iteration: usize, score: Option<f64>) -> Result<()> {
        let mut state = self.state.write().await;
        state.iteration_count = iteration;

        if let Some(new_score) = score {
            if state.best_score.map(|s| new_score > s).unwrap_or(true) {
                state.best_score = Some(new_score);
                state.last_improvement_iteration = iteration;
            }
        }

        Ok(())
    }

    pub async fn add_trigger(&self, trigger: Trigger) -> Result<()> {
        let mut triggers = self.triggers.write().await;
        triggers.push(trigger);
        Ok(())
    }

    pub async fn remove_trigger(&self, id: &str) -> Result<bool> {
        let mut triggers = self.triggers.write().await;
        let len = triggers.len();
        triggers.retain(|t| t.id != id);
        Ok(triggers.len() < len)
    }

    pub async fn enable_trigger(&self, id: &str) -> Result<bool> {
        let mut triggers = self.triggers.write().await;
        if let Some(trigger) = triggers.iter_mut().find(|t| t.id == id) {
            trigger.enabled = true;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    pub async fn disable_trigger(&self, id: &str) -> Result<bool> {
        let mut triggers = self.triggers.write().await;
        if let Some(trigger) = triggers.iter_mut().find(|t| t.id == id) {
            trigger.enabled = false;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    pub async fn execute_action(&self, action: &TriggerAction) -> Result<()> {
        match action {
            TriggerAction::Notify => {
                info!("Trigger notification");
            }
            TriggerAction::StopAgent => {
                info!("Stopping agent via trigger");
            }
            TriggerAction::SaveCheckpoint => {
                info!("Saving checkpoint via trigger");
            }
            TriggerAction::UpdateContext {
                section,
                content: _,
            } => {
                info!("Updating context section '{}' via trigger", section);
            }
            TriggerAction::ExecuteCommand { command } => {
                info!("Executing command via trigger: {}", command);
            }
            TriggerAction::Webhook { url } => {
                info!("Sending webhook via trigger: {}", url);
            }
        }
        Ok(())
    }
}
