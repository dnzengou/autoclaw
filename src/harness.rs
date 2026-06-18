use anyhow::{Result, Context as _};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use crate::agent::CodeChange;
use tracing::{debug, info, warn};

const ANTHROPIC_API_URL: &str = "https://api.anthropic.com/v1/messages";
const CLAUDE_MODEL: &str = "claude-sonnet-4-20250514";

pub struct ClaudeHarness {
    client: Client,
    api_key: String,
    model: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClaudeMessage {
    role: String,
    content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ClaudeResponse {
    content: Vec<ContentBlock>,
    usage: Usage,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ContentBlock {
    #[serde(rename = "type")]
    block_type: String,
    text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Usage {
    input_tokens: u32,
    output_tokens: u32,
}

impl ClaudeHarness {
    pub async fn new(api_key: Option<String>) -> Result<Self> {
        let api_key = api_key
            .or_else(|| std::env::var("ANTHROPIC_API_KEY").ok())
            .context("ANTHROPIC_API_KEY not set")?;
        
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()?;
        
        Ok(Self {
            client,
            api_key,
            model: CLAUDE_MODEL.to_string(),
        })
    }
    
    pub async fn generate_hypothesis(&self, context: &str, iteration: usize) -> Result<String> {
        let system_prompt = format!(
            r#"You are Autoclaw - an AI research agent.
            
ITERATION: {}

Generate ONE hypothesis to improve the system.
Rules:
- Be specific and testable
- Focus on single change
- Reference prior learnings from context
- Format: "If [change], then [expected outcome] because [reason]"

Respond with hypothesis only. No explanation."#,
            iteration
        );
        
        let response = self.call_claude(&system_prompt, context).await?;
        
        info!("Generated hypothesis: {}", response);
        Ok(response.trim().to_string())
    }
    
    pub async fn generate_changes(&self, context: &str, hypothesis: &str) -> Result<Vec<CodeChange>> {
        let system_prompt = r#"You are Autoclaw - an AI research agent implementing changes.

Generate code changes to test the hypothesis.
Output format (JSON):
{
  "changes": [
    {
      "file_path": "path/to/file",
      "diff": "full file content",
      "change_type": "add|modify|delete"
    }
  ]
}

Rules:
- Only modify train.py or specified files
- Keep changes minimal
- Ensure valid syntax
- No placeholders"#;
        
        let user_prompt = format!(
            "{context}\n\nHYPOTHESIS TO IMPLEMENT:\n{hypothesis}"
        );
        
        let response = self.call_claude(system_prompt, &user_prompt).await?;
        
        // Extract JSON from response
        let json_str = self.extract_json(&response)?;
        let parsed: Value = serde_json::from_str(&json_str)?;
        
        let mut changes = Vec::new();
        if let Some(changes_arr) = parsed.get("changes").and_then(|v| v.as_array()) {
            for change_val in changes_arr {
                let change = CodeChange {
                    file_path: change_val["file_path"].as_str().unwrap_or("").to_string(),
                    diff: change_val["diff"].as_str().unwrap_or("").to_string(),
                    change_type: match change_val["change_type"].as_str() {
                        Some("add") => crate::agent::ChangeType::Add,
                        Some("delete") => crate::agent::ChangeType::Delete,
                        _ => crate::agent::ChangeType::Modify,
                    },
                };
                changes.push(change);
            }
        }
        
        info!("Generated {} code changes", changes.len());
        Ok(changes)
    }
    
    pub async fn analyze_results(&self, context: &str, experiment_results: &[ExperimentResult]) -> Result<String> {
        let system_prompt = r#"You are Autoclaw - analyzing experiment results.

Analyze the experiment history and suggest:
1. What patterns emerged
2. What to try next
3. What to avoid

Respond in concise bullet points."#;
        
        let results_str = experiment_results.iter()
            .map(|r| format!("- {}: score={:.4}", r.hypothesis, r.score))
            .collect::<Vec<_>>()
            .join("\n");
        
        let user_prompt = format!(
            "{context}\n\nEXPERIMENT RESULTS:\n{results_str}"
        );
        
        self.call_claude(system_prompt, &user_prompt).await
    }
    
    async fn call_claude(&self, system: &str, user: &str) -> Result<String> {
        let request_body = json!({
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": user
                }
            ]
        });
        
        let response = self.client
            .post(ANTHROPIC_API_URL)
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("content-type", "application/json")
            .json(&request_body)
            .send()
            .await?;
        
        if !response.status().is_success() {
            let error_text = response.text().await?;
            anyhow::bail!("Claude API error: {}", error_text);
        }
        
        let claude_response: ClaudeResponse = response.json().await?;
        
        let text = claude_response.content
            .into_iter()
            .filter(|c| c.block_type == "text")
            .map(|c| c.text)
            .collect::<Vec<_>>()
            .join("\n");
        
        debug!(
            "Claude API call: input_tokens={}, output_tokens={}",
            claude_response.usage.input_tokens,
            claude_response.usage.output_tokens
        );
        
        Ok(text)
    }
    
    fn extract_json(&self, text: &str) -> Result<String> {
        // Find JSON block
        if let Some(start) = text.find('{') {
            if let Some(end) = text.rfind('}') {
                return Ok(text[start..=end].to_string());
            }
        }
        
        // Try to find JSON in code blocks
        if let Some(start) = text.find("```json") {
            let after_start = &text[start + 7..];
            if let Some(end) = after_start.find("```") {
                return Ok(after_start[..end].trim().to_string());
            }
        }
        
        anyhow::bail!("Could not extract JSON from response")
    }
}

#[derive(Debug, Clone)]
pub struct ExperimentResult {
    pub hypothesis: String,
    pub score: f64,
    pub iteration: usize,
}

// Tool definitions for Claude
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    pub name: String,
    pub description: String,
    pub input_schema: Value,
}

pub fn get_autoclaw_tools() -> Vec<Tool> {
    vec![
        Tool {
            name: "read_file".to_string(),
            description: "Read contents of a file".to_string(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }),
        },
        Tool {
            name: "write_file".to_string(),
            description: "Write content to a file".to_string(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }),
        },
        Tool {
            name: "execute_shell".to_string(),
            description: "Execute a shell command".to_string(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "number"}
                },
                "required": ["command"]
            }),
        },
        Tool {
            name: "git_commit".to_string(),
            description: "Commit changes to git".to_string(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            }),
        },
    ]
}
