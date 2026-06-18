use anyhow::Result;
use std::path::Path;
use tokio::fs;
use tracing::info;

pub async fn create_project(path: &str) -> Result<()> {
    let base_path = Path::new(path);
    fs::create_dir_all(base_path).await?;
    
    // Create directory structure
    let dirs = [".autoclaw", ".autoclaw/metrics", ".autoclaw/logs", ".autoclaw/checkpoints"];
    for dir in &dirs {
        fs::create_dir_all(base_path.join(dir)).await?;
    }
    
    // Create context.md
    let context_content = r#"# AUTOCALW CONTEXT

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
    fs::write(base_path.join("context.md"), context_content).await?;
    
    // Create eval_rubric.json
    let rubric_content = r#"{
  "name": "Autoclaw Default",
  "version": "1.0.0",
  "criteria": [
    {
      "id": "validation_loss",
      "name": "Validation Loss",
      "description": "Bits per byte on validation set",
      "metric_type": "lower_is_better",
      "target": 2.0,
      "weight": 0.4
    },
    {
      "id": "training_speed",
      "name": "Training Speed",
      "description": "Tokens processed per second",
      "metric_type": "higher_is_better",
      "target": 10000.0,
      "weight": 0.2
    },
    {
      "id": "memory_efficiency",
      "name": "Memory Efficiency",
      "description": "GPU memory utilization ratio",
      "metric_type": { "range": { "min": 0.7, "max": 0.95 } },
      "target": 0.85,
      "weight": 0.2
    },
    {
      "id": "code_quality",
      "name": "Code Quality",
      "description": "Static analysis score",
      "metric_type": "higher_is_better",
      "target": 0.9,
      "weight": 0.2
    }
  ],
  "weights": {
    "validation_loss": 0.4,
    "training_speed": 0.2,
    "memory_efficiency": 0.2,
    "code_quality": 0.2
  },
  "thresholds": {
    "excellent": 0.9,
    "good": 0.75,
    "acceptable": 0.6,
    "poor": 0.4
  }
}"#;
    fs::write(base_path.join("eval_rubric.json"), rubric_content).await?;
    
    // Create sample train.py
    let train_content = r#"# train.py - Agent modifies this file
# This is a minimal example - replace with your actual training code

import time
import json
import os

def train():
    # Simulated training loop
    best_loss = float('inf')
    
    for step in range(100):
        # Simulated loss that improves over time
        loss = 3.0 - (step / 100) * 1.5 + (0.1 * (step % 10))
        best_loss = min(best_loss, loss)
        
        print(f"Step {step}: loss={loss:.4f}")
        time.sleep(0.1)
    
    # Save metrics for evaluation
    metrics = {
        "val_bpb": best_loss,
        "training_speed": 5000.0,
        "memory_efficiency": 0.8,
        "code_quality": 0.85
    }
    
    os.makedirs(".autoclaw/metrics", exist_ok=True)
    with open(".autoclaw/metrics/latest.json", "w") as f:
        json.dump(metrics, f)
    
    return best_loss

if __name__ == "__main__":
    train()
"#;
    fs::write(base_path.join("train.py"), train_content).await?;
    
    // Create .gitignore
    let gitignore = r#".autoclaw/
__pycache__/
*.pyc
.env
*.log
"#;
    fs::write(base_path.join(".gitignore"), gitignore).await?;
    
    // Create README.md
    let readme = r#"# Autoclaw Project

Self-improving automation powered by Claude.

## Quick Start

1. Edit `context.md` to guide the AI
2. Run `autoclaw run` to start the loop
3. Check `.autoclaw/` for results

## Files

- `context.md` - Human-editable instructions
- `train.py` - AI-modified training code
- `eval_rubric.json` - Evaluation criteria
"#;
    fs::write(base_path.join("README.md"), readme).await?;
    
    info!("Created Autoclaw project at {}", path);
    Ok(())
}
