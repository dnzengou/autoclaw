use anyhow::{Result, Context as _};
use std::process::Command;
use tracing::{info, warn, error};

pub async fn deploy(target: &str) -> Result<()> {
    match target {
        "fly" => deploy_fly().await,
        "docker" => deploy_docker().await,
        "railway" => deploy_railway().await,
        "render" => deploy_render().await,
        _ => {
            warn!("Unknown deploy target: {}, using docker", target);
            deploy_docker().await
        }
    }
}

async fn deploy_fly() -> Result<()> {
    info!("Deploying to Fly.io...");
    
    // Check if fly.toml exists
    if !std::path::Path::new("fly.toml").exists() {
        // Create fly.toml
        let fly_toml = r#"app = "autoclaw-app"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8080"
  RUST_LOG = "info"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

[[vm]]
  size = "performance-2x"
  memory = "4gb"
"#;
        tokio::fs::write("fly.toml", fly_toml).await?;
    }
    
    // Run fly deploy
    let output = Command::new("fly")
        .args(["deploy"])
        .output()?;
    
    if output.status.success() {
        info!("Deployed to Fly.io successfully");
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        error!("Fly deploy failed: {}", stderr);
        anyhow::bail!("Fly deploy failed: {}", stderr)
    }
}

async fn deploy_docker() -> Result<()> {
    info!("Building Docker image...");
    
    // Create Dockerfile if not exists
    if !std::path::Path::new("Dockerfile").exists() {
        let dockerfile = r#"# Build stage
FROM rust:1.75-slim-bookworm as builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/autoclaw /usr/local/bin/autoclaw

ENV PORT=8080
ENV RUST_LOG=info

EXPOSE 8080

CMD ["autoclaw", "server"]
"#;
        tokio::fs::write("Dockerfile", dockerfile).await?;
    }
    
    // Build image
    let output = Command::new("docker")
        .args(["build", "-t", "autoclaw:latest", "."])
        .output()?;
    
    if output.status.success() {
        info!("Docker image built successfully");
        info!("Run with: docker run -p 8080:8080 autoclaw:latest");
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        error!("Docker build failed: {}", stderr);
        anyhow::bail!("Docker build failed: {}", stderr)
    }
}

async fn deploy_railway() -> Result<()> {
    info!("Deploying to Railway...");
    
    // Create railway.json if not exists
    if !std::path::Path::new("railway.json").exists() {
        let railway_json = r#"{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "autoclaw server",
    "healthcheckPath": "/api/status",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}"#;
        tokio::fs::write("railway.json", railway_json).await?;
    }
    
    let output = Command::new("railway")
        .args(["up"])
        .output()?;
    
    if output.status.success() {
        info!("Deployed to Railway successfully");
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        error!("Railway deploy failed: {}", stderr);
        anyhow::bail!("Railway deploy failed: {}", stderr)
    }
}

async fn deploy_render() -> Result<()> {
    info!("Deploying to Render...");
    
    // Create render.yaml if not exists
    if !std::path::Path::new("render.yaml").exists() {
        let render_yaml = r#"services:
  - type: web
    name: autoclaw
    runtime: docker
    repo: https://github.com/yourusername/autoclaw
    branch: main
    plan: standard
    envVars:
      - key: PORT
        value: 8080
      - key: RUST_LOG
        value: info
"#;
        tokio::fs::write("render.yaml", render_yaml).await?;
    }
    
    info!("Render configuration created. Push to GitHub and connect to Render.");
    Ok(())
}

pub fn generate_docker_compose() -> String {
    r#"version: '3.8'

services:
  autoclaw:
    build: .
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - RUST_LOG=info
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./context.md:/app/context.md
      - ./train.py:/app/train.py
      - ./.autoclaw:/app/.autoclaw
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
"#.to_string()
}

pub fn generate_github_actions() -> String {
    r#"name: Deploy Autoclaw

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Build
        run: cargo build --release
      
      - name: Deploy to Fly.io
        uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
"#.to_string()
}
