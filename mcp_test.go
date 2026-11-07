package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"
)

func mcpSession(t *testing.T, base string, lines ...string) []map[string]any {
	t.Helper()
	var out bytes.Buffer
	client := &mcpClient{base: base, http: &http.Client{Timeout: 5 * time.Second}}
	serveMCP(strings.NewReader(strings.Join(lines, "\n")+"\n"), &out, client)
	var resps []map[string]any
	dec := json.NewDecoder(&out)
	for dec.More() {
		var m map[string]any
		if err := dec.Decode(&m); err != nil {
			t.Fatalf("bad MCP output: %v", err)
		}
		resps = append(resps, m)
	}
	return resps
}

func TestMCPEndToEnd(t *testing.T) {
	dir := t.TempDir()
	cfg.WorkDir = dir
	os.WriteFile(filepath.Join(dir, "context.md"), []byte("# MISSION\nbeat baseline"), 0644)
	evo = NewEvoEngine(dir)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/status", handleStatus)
	mux.HandleFunc("/api/context", handleContext)
	mux.HandleFunc("/api/evo/status", handleEvoStatus)
	mux.HandleFunc("/api/evo/skills", handleEvoSkills)
	srv := httptest.NewServer(mux)
	defer srv.Close()

	resps := mcpSession(t, srv.URL,
		`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}`,
		`{"jsonrpc":"2.0","method":"notifications/initialized"}`,
		`{"jsonrpc":"2.0","id":2,"method":"tools/list"}`,
		`{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"autoclaw_get_context","arguments":{}}}`,
		`{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"evo_status","arguments":{}}}`,
		`{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"evo_import_skills","arguments":{"pack":{"version":1,"skills":[{"name":"warm","niche":"hyperparameters","strategy":"Sweep warmup 0.05-0.2."}]}}}}`,
		`{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"nope","arguments":{}}}`,
		`{"jsonrpc":"2.0","id":7,"method":"bogus"}`,
	)
	// The notification gets no response: 7 requests → 7 responses.
	if len(resps) != 7 {
		t.Fatalf("got %d responses, want 7", len(resps))
	}
	init := resps[0]["result"].(map[string]any)
	if init["protocolVersion"] != "2025-06-18" || init["serverInfo"].(map[string]any)["name"] != "autoclaw" {
		t.Fatalf("bad initialize result: %v", init)
	}
	if n := len(resps[1]["result"].(map[string]any)["tools"].([]any)); n != len(mcpTools()) {
		t.Fatalf("tools/list returned %d tools", n)
	}
	text := func(i int) string {
		r := resps[i]["result"].(map[string]any)
		if r["isError"] == true {
			t.Fatalf("response %d is an error: %v", i, r)
		}
		return r["content"].([]any)[0].(map[string]any)["text"].(string)
	}
	if !strings.Contains(text(2), "beat baseline") {
		t.Fatalf("context not returned: %q", text(2))
	}
	if !strings.Contains(text(3), `"population_size":5`) {
		t.Fatalf("evo status: %q", text(3))
	}
	if !strings.Contains(text(4), `"imported":1`) {
		t.Fatalf("import: %q", text(4))
	}
	if resps[5]["error"] == nil || resps[6]["error"].(map[string]any)["code"].(float64) != -32601 {
		t.Fatalf("unknown tool/method not rejected: %v / %v", resps[5], resps[6])
	}
}

func TestMCPServerDownIsToolError(t *testing.T) {
	resps := mcpSession(t, "http://127.0.0.1:1",
		`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"autoclaw_status","arguments":{}}}`)
	r := resps[0]["result"].(map[string]any)
	if r["isError"] != true {
		t.Fatalf("unreachable server should be a tool error, got %v", r)
	}
}

// Every route the server registers must be documented in the OpenAPI spec.
func TestOpenAPICoversRoutes(t *testing.T) {
	var spec struct {
		Paths map[string]any `json:"paths"`
	}
	if err := json.Unmarshal(openAPISpec, &spec); err != nil {
		t.Fatalf("openapi.json invalid: %v", err)
	}
	src, err := os.ReadFile("agent.go")
	if err != nil {
		t.Fatal(err)
	}
	for _, m := range regexp.MustCompile(`mux\.HandleFunc\("([^"]+)"`).FindAllStringSubmatch(string(src), -1) {
		route := m[1]
		if route == "/" || route == "/openapi.json" {
			continue
		}
		if _, ok := spec.Paths[route]; !ok {
			t.Errorf("route %s missing from site/openapi.json", route)
		}
	}
}
