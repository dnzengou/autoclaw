// mcp.go — `autoclaw mcp`: a Model Context Protocol server over stdio.
//
// Lets AI agents (Claude Code, Claude Desktop, Cursor, any MCP client) drive a
// running Autoclaw server: read status and results, steer context.md, start
// and stop the loop, and inspect or transfer EvoMetaClaw strategy genomes.
// Each tool call is forwarded to the server's HTTP API, so the MCP process
// holds no state of its own.
//
//	autoclaw mcp [--url http://localhost:8080]   (or AUTOCLAW_URL)
//
// Stdlib only. Protocol: newline-delimited JSON-RPC 2.0 on stdin/stdout;
// logs go to stderr.

package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const mcpProtocolVersion = "2025-06-18"

var mcpVersion = "0.9.0"

type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

// mcpTool describes one tool and how it maps onto the HTTP API.
type mcpTool struct {
	Name        string         `json:"name"`
	Title       string         `json:"title"`
	Description string         `json:"description"`
	InputSchema map[string]any `json:"inputSchema"`
	Annotations map[string]any `json:"annotations,omitempty"`

	call func(c *mcpClient, args map[string]any) (string, error) `json:"-"`
}

func objSchema(props map[string]any, required ...string) map[string]any {
	s := map[string]any{"type": "object", "properties": props, "additionalProperties": false}
	if len(required) > 0 {
		s["required"] = required
	}
	return s
}

var readOnly = map[string]any{"readOnlyHint": true, "openWorldHint": false}

func mcpTools() []mcpTool {
	return []mcpTool{
		{
			Name: "autoclaw_status", Title: "Loop status",
			Description: "Current state of the experiment loop: running, total experiments, best score, remaining budget (seconds), uptime.",
			InputSchema: objSchema(map[string]any{}), Annotations: readOnly,
			call: func(c *mcpClient, _ map[string]any) (string, error) { return c.do("GET", "/api/status", nil) },
		},
		{
			Name: "autoclaw_results", Title: "Experiment results",
			Description: "Experiments run so far (hypothesis, params, metrics, score, status, git hash, genome_id). Returns the most recent `limit` (default 20).",
			InputSchema: objSchema(map[string]any{
				"limit": map[string]any{"type": "integer", "minimum": 1, "maximum": 500, "description": "How many recent experiments to return."},
			}),
			Annotations: readOnly,
			call: func(c *mcpClient, a map[string]any) (string, error) {
				body, err := c.do("GET", "/api/results", nil)
				if err != nil {
					return "", err
				}
				var all []json.RawMessage
				if json.Unmarshal([]byte(body), &all) != nil {
					return body, nil
				}
				limit := intArg(a, "limit", 20)
				if len(all) > limit {
					all = all[len(all)-limit:]
				}
				out, _ := json.Marshal(all)
				return string(out), nil
			},
		},
		{
			Name: "autoclaw_get_context", Title: "Read context.md",
			Description: "Read context.md — the human-owned MISSION / CONSTRAINTS / HYPOTHESES / LEARNINGS file that steers what the loop tries.",
			InputSchema: objSchema(map[string]any{}), Annotations: readOnly,
			call: func(c *mcpClient, _ map[string]any) (string, error) { return c.do("GET", "/api/context", nil) },
		},
		{
			Name: "autoclaw_set_context", Title: "Replace context.md",
			Description: "Replace the whole of context.md. Read it first with autoclaw_get_context and send back the full edited text; the next iteration uses it.",
			InputSchema: objSchema(map[string]any{
				"content": map[string]any{"type": "string", "description": "Complete new context.md text."},
			}, "content"),
			Annotations: map[string]any{"destructiveHint": true, "idempotentHint": true},
			call: func(c *mcpClient, a map[string]any) (string, error) {
				content, _ := a["content"].(string)
				if strings.TrimSpace(content) == "" {
					return "", fmt.Errorf("content must not be empty")
				}
				return c.do("POST", "/api/context", strings.NewReader(content))
			},
		},
		{
			Name: "autoclaw_start", Title: "Start the loop",
			Description: "Start the experiment loop with a fresh time budget. Spends LLM API credits and runs train.py.",
			InputSchema: objSchema(map[string]any{}),
			Annotations: map[string]any{"destructiveHint": false, "idempotentHint": true},
			call:        func(c *mcpClient, _ map[string]any) (string, error) { return c.do("POST", "/api/start", nil) },
		},
		{
			Name: "autoclaw_stop", Title: "Stop the loop",
			Description: "Stop the experiment loop after the current experiment.",
			InputSchema: objSchema(map[string]any{}),
			Annotations: map[string]any{"destructiveHint": false, "idempotentHint": true},
			call:        func(c *mcpClient, _ map[string]any) (string, error) { return c.do("POST", "/api/stop", nil) },
		},
		{
			Name: "evo_status", Title: "Strategy population status",
			Description: "EvoMetaClaw population summary: size, trajectories, stagnation counter, circuit breaker, best proven genome, generations, retired count, genomes per niche.",
			InputSchema: objSchema(map[string]any{}), Annotations: readOnly,
			call: func(c *mcpClient, _ map[string]any) (string, error) { return c.do("GET", "/api/evo/status", nil) },
		},
		{
			Name: "evo_genomes", Title: "List strategy genomes",
			Description: "All strategy genomes with fitness, plays, wins, generation, parents and remembered winning hypotheses.",
			InputSchema: objSchema(map[string]any{}), Annotations: readOnly,
			call: func(c *mcpClient, _ map[string]any) (string, error) { return c.do("GET", "/api/evo/genomes", nil) },
		},
		{
			Name: "evo_lineage", Title: "Genome lineage",
			Description: "Ancestry of one genome, newest first, back to its generation-0 seed.",
			InputSchema: objSchema(map[string]any{
				"id": map[string]any{"type": "string", "description": "Genome id, e.g. evo-0007 or gen0-02."},
			}, "id"),
			Annotations: readOnly,
			call: func(c *mcpClient, a map[string]any) (string, error) {
				id, _ := a["id"].(string)
				return c.do("GET", "/api/evo/lineage?id="+url.QueryEscape(id), nil)
			},
		},
		{
			Name: "evo_export_skills", Title: "Export skill pack",
			Description: "Export proven strategy genomes as a portable SkillPack JSON (genomes with at least min_wins wins, default 1).",
			InputSchema: objSchema(map[string]any{
				"min_wins": map[string]any{"type": "integer", "minimum": 0, "description": "Minimum wins a genome needs to be exported."},
			}),
			Annotations: readOnly,
			call: func(c *mcpClient, a map[string]any) (string, error) {
				return c.do("GET", fmt.Sprintf("/api/evo/skills?min_wins=%d", intArg(a, "min_wins", 1)), nil)
			},
		},
		{
			Name: "evo_import_skills", Title: "Import skill pack",
			Description: "Import a SkillPack (from evo_export_skills on another workspace). New strategies join the population; duplicates merge their remembered wins.",
			InputSchema: objSchema(map[string]any{
				"pack": map[string]any{"type": "object", "description": "SkillPack JSON: {version, skills:[{name, niche, strategy, memories}]}."},
			}, "pack"),
			Annotations: map[string]any{"destructiveHint": false, "idempotentHint": true},
			call: func(c *mcpClient, a map[string]any) (string, error) {
				body, err := json.Marshal(a["pack"])
				if err != nil {
					return "", err
				}
				return c.do("POST", "/api/evo/skills", bytes.NewReader(body))
			},
		},
	}
}

func intArg(a map[string]any, key string, def int) int {
	if f, ok := a[key].(float64); ok && f >= 0 {
		return int(f)
	}
	return def
}

type mcpClient struct {
	base string
	http *http.Client
}

func (c *mcpClient) do(method, path string, body io.Reader) (string, error) {
	req, err := http.NewRequest(method, c.base+path, body)
	if err != nil {
		return "", err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return "", fmt.Errorf("autoclaw server not reachable at %s (start it with `autoclaw server`): %v", c.base, err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("%s %s: HTTP %d: %s", method, path, resp.StatusCode, strings.TrimSpace(string(data)))
	}
	return string(data), nil
}

func runMCP(args []string) {
	base := os.Getenv("AUTOCLAW_URL")
	for i := 0; i < len(args); i++ {
		if args[i] == "--url" && i+1 < len(args) {
			base = args[i+1]
			i++
		}
	}
	if base == "" {
		base = fmt.Sprintf("http://localhost:%d", cfg.Port)
	}
	client := &mcpClient{base: strings.TrimRight(base, "/"), http: &http.Client{Timeout: 30 * time.Second}}
	log.SetOutput(os.Stderr)
	log.Printf("MCP server on stdio → %s", client.base)
	serveMCP(os.Stdin, os.Stdout, client)
}

// serveMCP runs the JSON-RPC loop until in closes.
func serveMCP(in io.Reader, out io.Writer, client *mcpClient) {
	tools := mcpTools()
	byName := map[string]mcpTool{}
	for _, t := range tools {
		byName[t.Name] = t
	}
	enc := json.NewEncoder(out)
	sc := bufio.NewScanner(in)
	sc.Buffer(make([]byte, 64*1024), 8<<20)

	for sc.Scan() {
		line := bytes.TrimSpace(sc.Bytes())
		if len(line) == 0 {
			continue
		}
		var req rpcRequest
		if err := json.Unmarshal(line, &req); err != nil {
			enc.Encode(rpcResponse{JSONRPC: "2.0", ID: json.RawMessage("null"), Error: &rpcError{-32700, "parse error"}})
			continue
		}
		if len(req.ID) == 0 { // notification: never answered
			continue
		}
		resp := rpcResponse{JSONRPC: "2.0", ID: req.ID}
		switch req.Method {
		case "initialize":
			var p struct {
				ProtocolVersion string `json:"protocolVersion"`
			}
			json.Unmarshal(req.Params, &p)
			version := mcpProtocolVersion
			if p.ProtocolVersion != "" {
				version = p.ProtocolVersion
			}
			resp.Result = map[string]any{
				"protocolVersion": version,
				"capabilities":    map[string]any{"tools": map[string]any{"listChanged": false}},
				"serverInfo":      map[string]any{"name": "autoclaw", "title": "Autoclaw", "version": mcpVersion},
				"instructions": "Autoclaw runs a self-improving experiment loop: the human steers context.md, the AI proposes and runs " +
					"experiments, git keeps wins. Check autoclaw_status first; edit context.md to steer; use evo_* tools to inspect " +
					"which strategies are winning and to move proven ones between workspaces.",
			}
		case "ping":
			resp.Result = map[string]any{}
		case "tools/list":
			resp.Result = map[string]any{"tools": tools}
		case "tools/call":
			var p struct {
				Name      string         `json:"name"`
				Arguments map[string]any `json:"arguments"`
			}
			if err := json.Unmarshal(req.Params, &p); err != nil {
				resp.Error = &rpcError{-32602, "invalid params"}
				break
			}
			t, ok := byName[p.Name]
			if !ok {
				resp.Error = &rpcError{-32602, "unknown tool: " + p.Name}
				break
			}
			text, err := t.call(client, p.Arguments)
			if err != nil {
				resp.Result = map[string]any{"content": []map[string]any{{"type": "text", "text": err.Error()}}, "isError": true}
			} else {
				resp.Result = map[string]any{"content": []map[string]any{{"type": "text", "text": text}}}
			}
		default:
			resp.Error = &rpcError{-32601, "method not found: " + req.Method}
		}
		enc.Encode(resp)
	}
}
