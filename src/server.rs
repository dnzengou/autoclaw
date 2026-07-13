use axum::{
    extract::{Path, State},
    response::{Html, IntoResponse, Json},
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::RwLock;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;
use tracing::{error, info};

use crate::agent::{AgentConfig, AgentLoop};
use crate::eval::EvalRubric;
use crate::metrics::MetricsCollector;

const RUBRIC_PATH: &str = "eval_rubric.json";

pub struct APIServer {
    port: u16,
    state: Arc<ServerState>,
}

struct ServerState {
    agent: RwLock<Option<Arc<AgentLoop>>>,
    metrics: Arc<MetricsCollector>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct APIResponse<T> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
}

impl<T> APIResponse<T> {
    fn ok(data: T) -> Json<Self> {
        Json(Self {
            success: true,
            data: Some(data),
            error: None,
        })
    }

    fn err(message: impl Into<String>) -> Json<Self> {
        Json(Self {
            success: false,
            data: None,
            error: Some(message.into()),
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartRequest {
    pub context_path: Option<String>,
    pub budget_seconds: Option<u64>,
    pub headless: Option<bool>,
}

impl APIServer {
    pub async fn new(port: u16) -> anyhow::Result<Self> {
        let metrics = Arc::new(MetricsCollector::new().await?);

        let state = Arc::new(ServerState {
            agent: RwLock::new(None),
            metrics,
        });

        Ok(Self { port, state })
    }

    pub async fn run(&self) -> anyhow::Result<()> {
        let app = self.create_router();

        let addr = SocketAddr::from(([0, 0, 0, 0], self.port));
        info!("Starting API server on http://{}", addr);

        let listener = tokio::net::TcpListener::bind(addr).await?;
        axum::serve(listener, app).await?;

        Ok(())
    }

    fn create_router(&self) -> Router {
        Router::new()
            .route("/", get(Self::serve_dashboard))
            .route("/api/status", get(Self::get_status))
            .route("/api/start", post(Self::start_agent))
            .route("/api/stop", post(Self::stop_agent))
            .route("/api/experiments", get(Self::list_experiments))
            .route("/api/experiments/:id", get(Self::get_experiment))
            .route("/api/metrics", get(Self::get_metrics))
            .route("/api/metrics/prometheus", get(Self::get_prometheus))
            .route("/api/best", get(Self::get_best_result))
            .route(
                "/api/rubric",
                get(Self::get_rubric).post(Self::update_rubric),
            )
            .route(
                "/api/context",
                get(Self::get_context).post(Self::update_context),
            )
            .route("/ws", get(Self::websocket_handler))
            .layer(CorsLayer::permissive())
            .layer(TraceLayer::new_for_http())
            .with_state(self.state.clone())
    }

    async fn serve_dashboard() -> impl IntoResponse {
        // Serve the shared dashboard when running from the repo; otherwise
        // fall back to a minimal embedded page.
        match tokio::fs::read_to_string("dashboard.html").await {
            Ok(html) => Html(html),
            Err(_) => Html(FALLBACK_DASHBOARD_HTML.to_string()),
        }
    }

    async fn get_status(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let agent = state.agent.read().await;
        let (is_running, total, best) = match agent.as_ref() {
            Some(a) => {
                let experiments = a.get_experiments().await;
                let best = a.get_best_result().await.map(|r| r.score);
                (!a.is_stopping(), experiments.len(), best)
            }
            None => (false, 0, None),
        };

        APIResponse::ok(serde_json::json!({
            "is_running": is_running,
            "total_experiments": total,
            "best_score": best,
        }))
    }

    async fn start_agent(
        State(state): State<Arc<ServerState>>,
        Json(req): Json<StartRequest>,
    ) -> impl IntoResponse {
        if state.agent.read().await.is_some() {
            return APIResponse::err("Agent already running; stop it first");
        }

        info!("Starting agent via API");

        let config = AgentConfig {
            context_path: req.context_path.unwrap_or_else(|| "context.md".to_string()),
            budget_seconds: req.budget_seconds.unwrap_or(300),
            headless: req.headless.unwrap_or(true),
            ..Default::default()
        };

        match AgentLoop::new(config).await {
            Ok(agent) => {
                let agent = Arc::new(agent);
                *state.agent.write().await = Some(agent.clone());

                let state_clone = state.clone();
                tokio::spawn(async move {
                    if let Err(e) = agent.run().await {
                        error!("Agent error: {}", e);
                    }
                    // Loop finished: release the slot so a new run can start.
                    *state_clone.agent.write().await = None;
                });

                APIResponse::ok(serde_json::json!({"message": "Agent started"}))
            }
            Err(e) => APIResponse::err(e.to_string()),
        }
    }

    async fn stop_agent(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        match state.agent.read().await.as_ref() {
            Some(agent) => {
                agent.request_stop();
                info!("Stop requested via API");
                APIResponse::ok(serde_json::json!({"message": "Stop requested"}))
            }
            None => APIResponse::err("No agent running"),
        }
    }

    async fn list_experiments(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let agent = state.agent.read().await;
        let experiments = match agent.as_ref() {
            Some(a) => a.get_experiments().await,
            None => Vec::new(),
        };

        let summaries: Vec<serde_json::Value> = experiments
            .iter()
            .map(|e| {
                serde_json::json!({
                    "id": e.id,
                    "iteration": e.iteration,
                    "hypothesis": e.hypothesis,
                    "score": e.result.as_ref().map(|r| r.score),
                    "passed": e.result.as_ref().map(|r| r.passed).unwrap_or(false),
                    "timestamp": e.timestamp,
                })
            })
            .collect();

        APIResponse::ok(summaries)
    }

    async fn get_experiment(
        State(state): State<Arc<ServerState>>,
        Path(id): Path<String>,
    ) -> impl IntoResponse {
        let agent = state.agent.read().await;
        let experiments = match agent.as_ref() {
            Some(a) => a.get_experiments().await,
            None => Vec::new(),
        };

        match experiments.into_iter().find(|e| e.id == id) {
            Some(exp) => APIResponse::ok(exp),
            None => APIResponse::err("Experiment not found"),
        }
    }

    async fn get_metrics(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        APIResponse::ok(state.metrics.get_snapshot().await)
    }

    async fn get_prometheus(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let output = state.metrics.get_prometheus_output().await;
        ([("content-type", "text/plain; version=0.0.4")], output)
    }

    async fn get_best_result(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let agent = state.agent.read().await;
        let best = match agent.as_ref() {
            Some(a) => a.get_best_result().await,
            None => None,
        };
        APIResponse::ok(best)
    }

    async fn get_rubric() -> impl IntoResponse {
        match tokio::fs::read_to_string(RUBRIC_PATH).await {
            Ok(content) => match serde_json::from_str::<serde_json::Value>(&content) {
                Ok(rubric) => APIResponse::ok(rubric),
                Err(e) => APIResponse::err(format!("Invalid rubric file: {e}")),
            },
            Err(_) => APIResponse::err(format!("{RUBRIC_PATH} not found")),
        }
    }

    async fn update_rubric(Json(rubric): Json<EvalRubric>) -> impl IntoResponse {
        let content = match serde_json::to_string_pretty(&rubric) {
            Ok(c) => c,
            Err(e) => return APIResponse::err(e.to_string()),
        };
        match tokio::fs::write(RUBRIC_PATH, content).await {
            Ok(_) => APIResponse::ok(serde_json::json!({"message": "Rubric updated"})),
            Err(e) => APIResponse::err(e.to_string()),
        }
    }

    async fn get_context() -> impl IntoResponse {
        match tokio::fs::read_to_string("context.md").await {
            Ok(content) => APIResponse::ok(serde_json::json!({"content": content})),
            Err(e) => APIResponse::err(e.to_string()),
        }
    }

    async fn update_context(Json(body): Json<serde_json::Value>) -> impl IntoResponse {
        let Some(content) = body.get("content").and_then(|v| v.as_str()) else {
            return APIResponse::err("Missing content field");
        };
        match tokio::fs::write("context.md", content).await {
            Ok(_) => APIResponse::ok(serde_json::json!({"message": "Context updated"})),
            Err(e) => APIResponse::err(e.to_string()),
        }
    }

    async fn websocket_handler(
        State(state): State<Arc<ServerState>>,
        ws: axum::extract::WebSocketUpgrade,
    ) -> impl IntoResponse {
        ws.on_upgrade(|socket| handle_socket(socket, state))
    }
}

async fn handle_socket(mut socket: axum::extract::ws::WebSocket, state: Arc<ServerState>) {
    use axum::extract::ws::Message;

    loop {
        let metrics = state.metrics.get_snapshot().await;
        let update = serde_json::json!({
            "type": "metrics_update",
            "data": metrics,
        });

        if socket
            .send(Message::Text(update.to_string()))
            .await
            .is_err()
        {
            break;
        }

        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
    }
}

const FALLBACK_DASHBOARD_HTML: &str = r#"<!DOCTYPE html>
<html>
<head><title>Autoclaw</title></head>
<body style="font-family:system-ui;background:#0a0a0f;color:#e0e0e0;padding:2rem">
<h1>Autoclaw API</h1>
<p>dashboard.html not found next to the binary. API is live:</p>
<ul>
<li><a href="/api/status" style="color:#00ff88">/api/status</a></li>
<li><a href="/api/experiments" style="color:#00ff88">/api/experiments</a></li>
<li><a href="/api/metrics" style="color:#00ff88">/api/metrics</a></li>
</ul>
</body>
</html>"#;
