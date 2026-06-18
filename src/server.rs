use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
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
use tracing::{info, error};

use crate::agent::{AgentLoop, AgentConfig, AgentEvent, Experiment};
use crate::eval::{EvalResult, EvalRubric};
use crate::metrics::{MetricsCollector, MetricsStorage};

pub struct APIServer {
    port: u16,
    state: Arc<ServerState>,
}

struct ServerState {
    agent: Option<Arc<AgentLoop>>,
    metrics: Arc<MetricsCollector>,
    experiments: RwLock<Vec<Experiment>>,
    best_result: RwLock<Option<EvalResult>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct APIResponse<T> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartRequest {
    pub context_path: Option<String>,
    pub budget_seconds: Option<u64>,
    pub headless: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardData {
    pub metrics: MetricsStorage,
    pub experiments: Vec<ExperimentSummary>,
    pub best_score: Option<f64>,
    pub is_running: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExperimentSummary {
    pub id: String,
    pub iteration: usize,
    pub score: Option<f64>,
    pub passed: bool,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl APIServer {
    pub async fn new(port: u16) -> anyhow::Result<Self> {
        let metrics = Arc::new(MetricsCollector::new().await?);
        
        let state = Arc::new(ServerState {
            agent: None,
            metrics,
            experiments: RwLock::new(Vec::new()),
            best_result: RwLock::new(None),
        });
        
        Ok(Self { port, state })
    }
    
    pub async fn run(&self) -> anyhow::Result<()> {
        let app = self.create_router().await?;
        
        let addr = SocketAddr::from(([0, 0, 0, 0], self.port));
        info!("Starting API server on http://{}", addr);
        
        let listener = tokio::net::TcpListener::bind(addr).await?;
        axum::serve(listener, app).await?;
        
        Ok(())
    }
    
    async fn create_router(&self) -> anyhow::Result<Router> {
        let state = self.state.clone();
        
        let app = Router::new()
            // Dashboard
            .route("/", get(Self::serve_dashboard))
            .route("/dashboard", get(Self::serve_dashboard))
            
            // API endpoints
            .route("/api/status", get(Self::get_status))
            .route("/api/start", post(Self::start_agent))
            .route("/api/stop", post(Self::stop_agent))
            .route("/api/experiments", get(Self::list_experiments))
            .route("/api/experiments/:id", get(Self::get_experiment))
            .route("/api/metrics", get(Self::get_metrics))
            .route("/api/metrics/prometheus", get(Self::get_prometheus))
            .route("/api/best", get(Self::get_best_result))
            .route("/api/rubric", get(Self::get_rubric))
            .route("/api/rubric", post(Self::update_rubric))
            .route("/api/context", get(Self::get_context))
            .route("/api/context", post(Self::update_context))
            
            // WebSocket for real-time updates
            .route("/ws", get(Self::websocket_handler))
            
            .layer(CorsLayer::permissive())
            .layer(TraceLayer::new_for_http())
            .with_state(state);
        
        Ok(app)
    }
    
    async fn serve_dashboard() -> impl IntoResponse {
        Html(DASHBOARD_HTML)
    }
    
    async fn get_status(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let is_running = state.agent.is_some();
        let experiments = state.experiments.read().await;
        let best = state.best_result.read().await;
        
        let response = serde_json::json!({
            "is_running": is_running,
            "total_experiments": experiments.len(),
            "best_score": best.as_ref().map(|r| r.score),
        });
        
        Json(APIResponse {
            success: true,
            data: Some(response),
            error: None,
        })
    }
    
    async fn start_agent(
        State(state): State<Arc<ServerState>>,
        Json(req): Json<StartRequest>,
    ) -> impl IntoResponse {
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
                // Start agent in background
                let agent_clone = agent.clone();
                tokio::spawn(async move {
                    if let Err(e) = agent_clone.run().await {
                        error!("Agent error: {}", e);
                    }
                });
                
                Json(APIResponse {
                    success: true,
                    data: Some(serde_json::json!({"message": "Agent started"})),
                    error: None,
                })
            }
            Err(e) => {
                Json(APIResponse {
                    success: false,
                    data: None,
                    error: Some(e.to_string()),
                })
            }
        }
    }
    
    async fn stop_agent(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        info!("Stopping agent via API");
        // Implementation would signal agent to stop
        
        Json(APIResponse {
            success: true,
            data: Some(serde_json::json!({"message": "Agent stopped"})),
            error: None,
        })
    }
    
    async fn list_experiments(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let experiments = state.experiments.read().await;
        let summaries: Vec<ExperimentSummary> = experiments
            .iter()
            .map(|e| ExperimentSummary {
                id: e.id.clone(),
                iteration: e.iteration,
                score: e.result.as_ref().map(|r| r.score),
                passed: e.result.as_ref().map(|r| r.passed).unwrap_or(false),
                timestamp: e.timestamp,
            })
            .collect();
        
        Json(APIResponse {
            success: true,
            data: Some(summaries),
            error: None,
        })
    }
    
    async fn get_experiment(
        State(state): State<Arc<ServerState>>,
        Path(id): Path<String>,
    ) -> impl IntoResponse {
        let experiments = state.experiments.read().await;
        
        match experiments.iter().find(|e| e.id == id) {
            Some(exp) => Json(APIResponse {
                success: true,
                data: Some(exp.clone()),
                error: None,
            }),
            None => Json(APIResponse {
                success: false,
                data: None,
                error: Some("Experiment not found".to_string()),
            }),
        }
    }
    
    async fn get_metrics(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let metrics = state.metrics.get_snapshot().await;
        
        Json(APIResponse {
            success: true,
            data: Some(metrics),
            error: None,
        })
    }
    
    async fn get_prometheus(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let output = state.metrics.get_prometheus_output()
            .unwrap_or_else(|| "# No metrics available".to_string());
        
        ([("content-type", "text/plain")], output)
    }
    
    async fn get_best_result(State(state): State<Arc<ServerState>>) -> impl IntoResponse {
        let best = state.best_result.read().await;
        
        Json(APIResponse {
            success: true,
            data: best.clone(),
            error: None,
        })
    }
    
    async fn get_rubric() -> impl IntoResponse {
        // Return default rubric
        Json(APIResponse {
            success: true,
            data: Some(serde_json::json!({})),
            error: None,
        })
    }
    
    async fn update_rubric(Json(rubric): Json<EvalRubric>) -> impl IntoResponse {
        // Save rubric
        Json(APIResponse {
            success: true,
            data: Some(serde_json::json!({"message": "Rubric updated"})),
            error: None,
        })
    }
    
    async fn get_context() -> impl IntoResponse {
        // Read context.md
        match tokio::fs::read_to_string("context.md").await {
            Ok(content) => Json(APIResponse {
                success: true,
                data: Some(serde_json::json!({"content": content})),
                error: None,
            }),
            Err(e) => Json(APIResponse {
                success: false,
                data: None,
                error: Some(e.to_string()),
            }),
        }
    }
    
    async fn update_context(Json(body): Json<serde_json::Value>) -> impl IntoResponse {
        if let Some(content) = body.get("content").and_then(|v| v.as_str()) {
            match tokio::fs::write("context.md", content).await {
                Ok(_) => Json(APIResponse {
                    success: true,
                    data: Some(serde_json::json!({"message": "Context updated"})),
                    error: None,
                }),
                Err(e) => Json(APIResponse {
                    success: false,
                    data: None,
                    error: Some(e.to_string()),
                }),
            }
        } else {
            Json(APIResponse {
                success: false,
                data: None,
                error: Some("Missing content field".to_string()),
            })
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
    
    // Send initial state
    let metrics = state.metrics.get_snapshot().await;
    let init_msg = serde_json::json!({
        "type": "init",
        "data": metrics,
    });
    
    let _ = socket.send(Message::Text(init_msg.to_string())).await;
    
    // Keep connection alive and send updates
    loop {
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        
        let metrics = state.metrics.get_snapshot().await;
        let update = serde_json::json!({
            "type": "metrics_update",
            "data": metrics,
        });
        
        if socket.send(Message::Text(update.to_string())).await.is_err() {
            break;
        }
    }
}

const DASHBOARD_HTML: &str = r#"<!DOCTYPE html>
<html>
<head>
    <title>Autoclaw Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid #333;
            margin-bottom: 30px;
        }
        h1 { font-size: 2rem; color: #00ff88; }
        .status { display: flex; gap: 10px; align-items: center; }
        .status-dot {
            width: 12px; height: 12px;
            border-radius: 50%;
            background: #333;
        }
        .status-dot.running { background: #00ff88; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #15151a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
        }
        .metric-card h3 {
            color: #888;
            font-size: 0.875rem;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #fff;
        }
        .metric-value.positive { color: #00ff88; }
        .metric-value.negative { color: #ff4444; }
        
        .controls {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #00ff88;
            color: #0a0a0f;
        }
        .btn-primary:hover { background: #00cc6a; }
        .btn-danger {
            background: #ff4444;
            color: #fff;
        }
        .btn-danger:hover { background: #cc3333; }
        
        .experiments-list {
            background: #15151a;
            border: 1px solid #333;
            border-radius: 12px;
            overflow: hidden;
        }
        .experiments-list h2 {
            padding: 20px;
            border-bottom: 1px solid #333;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px 20px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        th {
            color: #888;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
        }
        tr:hover { background: #1a1a20; }
        .badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-success { background: #00ff8822; color: #00ff88; }
        .badge-fail { background: #ff444422; color: #ff4444; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Autoclaw</h1>
            <div class="status">
                <span class="status-dot" id="statusDot"></span>
                <span id="statusText">Idle</span>
            </div>
        </header>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Total Experiments</h3>
                <div class="metric-value" id="totalExp">0</div>
            </div>
            <div class="metric-card">
                <h3>Success Rate</h3>
                <div class="metric-value positive" id="successRate">0%</div>
            </div>
            <div class="metric-card">
                <h3>Best Score</h3>
                <div class="metric-value" id="bestScore">-</div>
            </div>
            <div class="metric-card">
                <h3>Current Iteration</h3>
                <div class="metric-value" id="currentIter">0</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn-primary" onclick="startAgent()">Start</button>
            <button class="btn-danger" onclick="stopAgent()">Stop</button>
        </div>
        
        <div class="experiments-list">
            <h2>Recent Experiments</h2>
            <table>
                <thead>
                    <tr>
                        <th>Iteration</th>
                        <th>Hypothesis</th>
                        <th>Score</th>
                        <th>Duration</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="experimentsTable">
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        let ws = null;
        
        function connect() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                updateDashboard(msg);
            };
            ws.onclose = () => setTimeout(connect, 1000);
        }
        
        function updateDashboard(msg) {
            if (msg.type === 'metrics_update' || msg.type === 'init') {
                const data = msg.data;
                document.getElementById('totalExp').textContent = data.experiments_total || 0;
                document.getElementById('currentIter').textContent = data.current_iteration || 0;
                document.getElementById('bestScore').textContent = 
                    data.best_score ? data.best_score.toFixed(4) : '-';
                
                const total = data.experiments_total || 0;
                const success = data.experiments_successful || 0;
                const rate = total > 0 ? ((success / total) * 100).toFixed(1) : 0;
                document.getElementById('successRate').textContent = rate + '%';
            }
        }
        
        async function startAgent() {
            await fetch('/api/start', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({}) });
            document.getElementById('statusDot').classList.add('running');
            document.getElementById('statusText').textContent = 'Running';
        }
        
        async function stopAgent() {
            await fetch('/api/stop', { method: 'POST' });
            document.getElementById('statusDot').classList.remove('running');
            document.getElementById('statusText').textContent = 'Idle';
        }
        
        connect();
    </script>
</body>
</html>"#;
