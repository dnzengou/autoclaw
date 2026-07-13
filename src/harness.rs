use anyhow::{Context as _, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::{debug, info};

use crate::agent::CodeChange;

const ANTHROPIC_API_URL: &str = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL: &str = "claude-opus-4-8";

pub struct ClaudeHarness {
    client: Client,
    api_key: String,
    model: String,
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
    #[serde(default)]
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

        let model = std::env::var("AUTOCLAW_MODEL").unwrap_or_else(|_| DEFAULT_MODEL.to_string());

        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(300))
            .build()?;

        Ok(Self {
            client,
            api_key,
            model,
        })
    }

    pub async fn generate_hypothesis(&self, context: &str, iteration: usize) -> Result<String> {
        let system_prompt = format!(
            r#"You are Autoclaw - an AI research agent.

ITERATION: {iteration}

Generate ONE hypothesis to improve the system.
Rules:
- Be specific and testable
- Focus on single change
- Reference prior learnings from context
- Format: "If [change], then [expected outcome] because [reason]"

Respond with hypothesis only. No explanation."#
        );

        let response = self.call_claude(&system_prompt, context).await?;

        info!("Generated hypothesis: {}", response);
        Ok(response.trim().to_string())
    }

    pub async fn generate_changes(
        &self,
        context: &str,
        hypothesis: &str,
    ) -> Result<Vec<CodeChange>> {
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

        let user_prompt = format!("{context}\n\nHYPOTHESIS TO IMPLEMENT:\n{hypothesis}");

        let response = self.call_claude(system_prompt, &user_prompt).await?;

        let json_str = self.extract_json(&response)?;
        let parsed: Value = serde_json::from_str(&json_str)?;

        let mut changes = Vec::new();
        if let Some(changes_arr) = parsed.get("changes").and_then(|v| v.as_array()) {
            for change_val in changes_arr {
                changes.push(CodeChange {
                    file_path: change_val["file_path"].as_str().unwrap_or("").to_string(),
                    diff: change_val["diff"].as_str().unwrap_or("").to_string(),
                    change_type: match change_val["change_type"].as_str() {
                        Some("add") => crate::agent::ChangeType::Add,
                        Some("delete") => crate::agent::ChangeType::Delete,
                        _ => crate::agent::ChangeType::Modify,
                    },
                });
            }
        }

        info!("Generated {} code changes", changes.len());
        Ok(changes)
    }

    async fn call_claude(&self, system: &str, user: &str) -> Result<String> {
        let request_body = json!({
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{ "role": "user", "content": user }]
        });

        let response = self
            .client
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

        let text = claude_response
            .content
            .into_iter()
            .filter(|c| c.block_type == "text")
            .map(|c| c.text)
            .collect::<Vec<_>>()
            .join("\n");

        debug!(
            "Claude API call: input_tokens={}, output_tokens={}",
            claude_response.usage.input_tokens, claude_response.usage.output_tokens
        );

        Ok(text)
    }

    fn extract_json(&self, text: &str) -> Result<String> {
        // Prefer a fenced ```json block; fall back to outermost braces.
        if let Some(start) = text.find("```json") {
            let after_start = &text[start + 7..];
            if let Some(end) = after_start.find("```") {
                return Ok(after_start[..end].trim().to_string());
            }
        }

        if let (Some(start), Some(end)) = (text.find('{'), text.rfind('}')) {
            if start < end {
                return Ok(text[start..=end].to_string());
            }
        }

        anyhow::bail!("Could not extract JSON from response")
    }
}
