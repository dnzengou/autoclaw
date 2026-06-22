// autoclaw — Self-improving AI experiment loop (Go version)
//
// Usage:
//   go build -o autoclaw agent.go
//   ./autoclaw --budget 300 --model deepseek-chat --port 8080
//
// DeepSeek: Set DEEPSEEK_API_KEY env var
// Also supports: ANTHROPIC_API_KEY, OPENAI_API_KEY
//
// Features:
//   - Built-in HTTPS (Go's own TLS stack, no system libs needed)
//   - DeepSeek, Claude, GPT, or heuristic fallback
//   - Live dashboard with SSE, charts, context editor
//   - Git-native experiment tracking
//   - Cross-compiles to any platform

package main

import (
	"bufio"
	"bytes"
	"crypto/rand"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"math/big"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// ─── Configuration ──────────────────────────────────────────────────────────

type Config struct {
	Budget     int    // Total experiment budget in seconds
	Model      string // LLM model name
	Hypotheses int    // Hypotheses per iteration
	Port       int    // Dashboard HTTP port
	RubricPath string // Path to rubric JSON
	NoDashboard bool
	WorkDir    string // Working directory
}

// ─── Data Model ─────────────────────────────────────────────────────────────

type Experiment struct {
	ID              string            `json:"id"`
	Hypothesis      string            `json:"hypothesis"`
	Params          map[string]any    `json:"params"`
	Metrics         map[string]any    `json:"metrics"`
	Score           float64           `json:"score"`
	Status          string            `json:"status"`
	Timestamp       string            `json:"timestamp"`
	GitHash         string            `json:"git_hash"`
	DurationSeconds float64           `json:"duration_seconds"`
	BudgetRemaining float64           `json:"budget_remaining,omitempty"`
}

type Rubric struct {
	PrimaryMetric    string             `json:"primary_metric"`
	HigherIsBetter   bool               `json:"higher_is_better"`
	SecondaryMetrics []string           `json:"secondary_metrics"`
	Weights          map[string]float64 `json:"weights"`
	PassThreshold    float64            `json:"pass_threshold"`
	FailThreshold    float64            `json:"fail_threshold"`
	Scoring          string             `json:"scoring"`
}

type Status struct {
	Running         bool    `json:"running"`
	TotalExperiments int    `json:"total_experiments"`
	BestScore       float64 `json:"best_score"`
	BudgetRemaining float64 `json:"budget_remaining"`
	Uptime          float64 `json:"uptime"`
}

// ─── Global State ───────────────────────────────────────────────────────────

var (
	cfg          Config
	experiments  []Experiment
	experimentsMu sync.RWMutex
	bestScore    float64
	nextExpID    int
	budgetRemaining float64
	loopStartTime time.Time
	running      bool
	stopCh       chan struct{}
	sseClients   []chan Experiment
	sseMu        sync.Mutex
)

// ─── Main ───────────────────────────────────────────────────────────────────

func main() {
	log.SetFlags(log.Ltime | log.Lmsgprefix)
	log.SetPrefix("[autoclaw] ")

	// Parse flags
	cfg = Config{
		Budget:     300,
		Model:      "deepseek-chat",
		Hypotheses: 3,
		Port:       8080,
		RubricPath: "rubric.json",
		WorkDir:    ".",
	}

	for i := 1; i < len(os.Args); i++ {
		switch os.Args[i] {
		case "--budget":
			if i+1 < len(os.Args) { cfg.Budget = atoi(os.Args[i+1]); i++ }
		case "--model":
			if i+1 < len(os.Args) { cfg.Model = os.Args[i+1]; i++ }
		case "--hypotheses":
			if i+1 < len(os.Args) { cfg.Hypotheses = atoi(os.Args[i+1]); i++ }
		case "--port":
			if i+1 < len(os.Args) { cfg.Port = atoi(os.Args[i+1]); i++ }
		case "--rubric":
			if i+1 < len(os.Args) { cfg.RubricPath = os.Args[i+1]; i++ }
		case "--no-dashboard":
			cfg.NoDashboard = true
		case "--work-dir":
			if i+1 < len(os.Args) { cfg.WorkDir = os.Args[i+1]; i++ }
		}
	}

	// Ensure work dir exists
	os.MkdirAll(filepath.Join(cfg.WorkDir, "experiments"), 0755)

	// Load existing results
	loadResults()

	// Init git
	gitInit()

	stopCh = make(chan struct{})

	// Start dashboard HTTP server
	if !cfg.NoDashboard {
		go startHTTPServer()
		log.Printf("Dashboard: http://localhost:%d", cfg.Port)
		log.Printf("API:       http://localhost:%d/api/results", cfg.Port)
		log.Printf("SSE:       http://localhost:%d/events", cfg.Port)
	}

	log.Printf("Autoclaw Agent Loop ready")
	log.Printf("Budget: %ds | Model: %s | Hypotheses/iter: %d", cfg.Budget, cfg.Model, cfg.Hypotheses)
	log.Printf("Past experiments loaded: %d", len(experiments))
	log.Println("Commands: start, stop, status, quit")

	// Handle signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Println("Shutting down...")
		close(stopCh)
		os.Exit(0)
	}()

	// Interactive CLI
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		cmd := strings.TrimSpace(scanner.Text())
		switch cmd {
		case "start":
			if !running {
				running = true
				budgetRemaining = float64(cfg.Budget)
				loopStartTime = time.Now()
				go mainLoop()
				log.Println("Loop started.")
			} else {
				log.Println("Already running.")
			}
		case "stop":
			if running {
				close(stopCh)
				stopCh = make(chan struct{})
				running = false
				log.Println("Stop signal sent.")
			}
		case "status":
			experimentsMu.RLock()
			n := len(experiments)
			bs := bestScore
			experimentsMu.RUnlock()
			log.Printf("Running: %v | Experiments: %d | Best: %.4f | Budget left: %.1fs",
				running, n, bs, budgetRemaining)
		case "quit":
			log.Println("Shutting down.")
			os.Exit(0)
		}
	}
}

// ─── Main Loop ──────────────────────────────────────────────────────────────

func mainLoop() {
	defer func() { running = false }()

	iteration := 0
	for {
		select {
		case <-stopCh:
			return
		default:
		}

		if budgetRemaining <= 0 {
			log.Printf("Budget exhausted after %.1fs", time.Since(loopStartTime).Seconds())
			return
		}

		iteration++
		context := readContext()
		pastResults := summarizeResults()

		log.Printf("Iteration %d — Generating hypotheses...", iteration)

		// Generate hypotheses
		hypotheses := generateHypotheses(context, pastResults)
		if len(hypotheses) == 0 {
			log.Println("No hypotheses generated, stopping.")
			return
		}

		log.Printf("Generated %d hypotheses", len(hypotheses))

		// Run each hypothesis
		for _, h := range hypotheses {
			select {
			case <-stopCh:
				return
			default:
			}

			if budgetRemaining <= 0 {
				return
			}

			expStart := time.Now()
			result := runExperiment(h)
			elapsed := time.Since(expStart).Seconds()
			budgetRemaining -= elapsed
			result.BudgetRemaining = budgetRemaining

			// Append to results
			experimentsMu.Lock()
			experiments = append(experiments, result)
			if result.Score > bestScore {
				bestScore = result.Score
				gitTag(fmt.Sprintf("best-%s", result.ID))
			}
			experimentsMu.Unlock()
			saveResults()
			broadcastSSE(result)

			log.Printf("%s: score=%.4f, status=%s, budget_left=%.1fs",
				result.ID, result.Score, result.Status, budgetRemaining)
		}

		time.Sleep(1 * time.Second)
	}
}

// ─── Hypothesis Generation ──────────────────────────────────────────────────

type Hypothesis struct {
	Hypothesis string         `json:"hypothesis"`
	Params     map[string]any `json:"params"`
}

func generateHypotheses(context, pastResults string) []Hypothesis {
	// Try LLM API first
	if key := os.Getenv("DEEPSEEK_API_KEY"); key != "" {
		if h := callDeepSeek(key, context, pastResults); len(h) > 0 {
			return h
		}
	}
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		if h := callAnthropic(key, context, pastResults); len(h) > 0 {
			return h
		}
	}
	if key := os.Getenv("OPENAI_API_KEY"); key != "" {
		if h := callOpenAI(key, context, pastResults); len(h) > 0 {
			return h
		}
	}

	// Fallback: heuristic generator
	return fallbackHypotheses()
}

func callDeepSeek(apiKey, context, pastResults string) []Hypothesis {
	prompt := buildPrompt(context, pastResults)
	body := map[string]any{
		"model": cfg.Model,
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
		"max_tokens": 2000,
		"temperature": 0.7,
	}
	return callLLMAPI("https://api.deepseek.com/chat/completions", apiKey, body, "deepseek")
}

func callAnthropic(apiKey, context, pastResults string) []Hypothesis {
	prompt := buildPrompt(context, pastResults)
	body := map[string]any{
		"model":       "claude-3-opus",
		"max_tokens":  2000,
		"messages":    []map[string]string{{"role": "user", "content": prompt}},
	}
	return callLLMAPI("https://api.anthropic.com/v1/messages", apiKey, body, "anthropic")
}

func callOpenAI(apiKey, context, pastResults string) []Hypothesis {
	prompt := buildPrompt(context, pastResults)
	body := map[string]any{
		"model":       cfg.Model,
		"messages":    []map[string]string{{"role": "user", "content": prompt}},
		"max_tokens":  2000,
	}
	return callLLMAPI("https://api.openai.com/v1/chat/completions", apiKey, body, "openai")
}

func callLLMAPI(url, apiKey string, body map[string]any, provider string) []Hypothesis {
	jsonBody, err := json.Marshal(body)
	if err != nil {
		log.Printf("LLM marshal error: %v", err)
		return nil
	}

	req, err := http.NewRequest("POST", url, bytes.NewReader(jsonBody))
	if err != nil {
		log.Printf("LLM request error: %v", err)
		return nil
	}

	req.Header.Set("Content-Type", "application/json")
	switch provider {
	case "deepseek":
		req.Header.Set("Authorization", "Bearer "+apiKey)
	case "anthropic":
		req.Header.Set("x-api-key", apiKey)
		req.Header.Set("anthropic-version", "2023-06-01")
	case "openai":
		req.Header.Set("Authorization", "Bearer "+apiKey)
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("LLM API error (%s): %v", provider, err)
		return nil
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		log.Printf("LLM API error (%s): %d %s", provider, resp.StatusCode, string(respBody[:min(len(respBody), 300)]))
		return nil
	}

	// Parse response
	var hypotheses []Hypothesis

	switch provider {
	case "anthropic":
		var anon struct {
			Content []struct {
				Text string `json:"text"`
			} `json:"content"`
		}
		if err := json.Unmarshal(respBody, &anon); err != nil {
			log.Printf("LLM parse error: %v", err)
			return nil
		}
		if len(anon.Content) > 0 {
			hypotheses = parseHypothesesJSON(anon.Content[0].Text)
		}
	default:
		var anon struct {
			Choices []struct {
				Message struct {
					Content string `json:"content"`
				} `json:"message"`
			} `json:"choices"`
		}
		if err := json.Unmarshal(respBody, &anon); err != nil {
			log.Printf("LLM parse error: %v", err)
			return nil
		}
		if len(anon.Choices) > 0 {
			hypotheses = parseHypothesesJSON(anon.Choices[0].Message.Content)
		}
	}

	return hypotheses
}

func buildPrompt(context, pastResults string) string {
	return fmt.Sprintf(`You are an AI research scientist running experiments to optimize a model.

## Context (human's goals and constraints)
%s

## Past Experiment Results
%s

Generate %d distinct hypotheses for the next experiments.
Each hypothesis must include specific parameter changes.

Return ONLY a JSON array of objects with keys: "hypothesis" (string) and "params" (dict).
Example:
[
  {"hypothesis": "Increase learning rate to 3e-5 with cosine decay", "params": {"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3}}
]

Generate %d hypotheses now:`, context, pastResults, cfg.Hypotheses, cfg.Hypotheses)
}

func parseHypothesesJSON(text string) []Hypothesis {
	// Try to find JSON array in the response
	re := regexp.MustCompile(`\[\s*\{.*\}\s*\]`)
	match := re.FindString(text)
	if match != "" {
		var h []Hypothesis
		if err := json.Unmarshal([]byte(match), &h); err == nil {
			return h
		}
	}

	// Try parsing whole text as JSON
	var h []Hypothesis
	if err := json.Unmarshal([]byte(text), &h); err == nil {
		return h
	}

	return nil
}

func fallbackHypotheses() []Hypothesis {
	return []Hypothesis{
		{
			Hypothesis: "Try learning rate 2e-5 with linear warmup (10% of steps)",
			Params:     map[string]any{"lr": 2e-5, "warmup_ratio": 0.1, "batch_size": 16, "epochs": 3},
		},
		{
			Hypothesis: "Increase learning rate to 3e-5 with cosine decay schedule",
			Params:     map[string]any{"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3},
		},
		{
			Hypothesis: "Add random word dropout augmentation (rate=0.1) during training",
			Params:     map[string]any{"lr": 2e-5, "batch_size": 16, "epochs": 3, "augmentation": "word_dropout", "aug_rate": 0.1},
		},
	}
}

// ─── Experiment Runner ──────────────────────────────────────────────────────

func runExperiment(h Hypothesis) Experiment {
	expID := fmt.Sprintf("exp-%03d", nextExpID)
	nextExpID++
	expDir := filepath.Join(cfg.WorkDir, "experiments", expID)
	os.MkdirAll(expDir, 0755)

	log.Printf("Running %s: %s", expID, h.Hypothesis)

	start := time.Now()

	// Run train.py
	var metrics map[string]any
	trainScript := filepath.Join(cfg.WorkDir, "train.py")

	if _, err := os.Stat(trainScript); err == nil {
		args := []string{trainScript, "--output-dir", expDir}
		for k, v := range h.Params {
			args = append(args, "--"+strings.ReplaceAll(k, "_", "-"), fmt.Sprintf("%v", v))
		}

		cmd := exec.Command("python3", args...)
		cmd.Dir = cfg.WorkDir
		output, err := cmd.Output()
		if err != nil {
			log.Printf("%s: train.py error: %v", expID, err)
			metrics = map[string]any{"error": err.Error()}
		} else {
			json.Unmarshal(output, &metrics)
		}
	} else {
		// Simulated training
		time.Sleep(time.Duration(1+randInt(3)) * time.Second)
		metrics = map[string]any{
			"f1_score":         0.82 + float64(randInt(5))/100,
			"accuracy":         0.83,
			"inference_time_ms": 1.5,
		}
	}

	duration := time.Since(start).Seconds()

	// Save metrics
	if metrics != nil {
		data, _ := json.MarshalIndent(metrics, "", "  ")
		os.WriteFile(filepath.Join(expDir, "metrics.json"), data, 0644)
	}
	paramsData, _ := json.MarshalIndent(h.Params, "", "  ")
	os.WriteFile(filepath.Join(expDir, "params.json"), paramsData, 0644)

	// Score
	rubric := loadRubric()
	score := computeScore(metrics, rubric)

	// Determine status
	status := "completed"
	if score < bestScore+rubric.FailThreshold {
		status = "reverted"
	}

	// Git
	gitCommit(expID, h.Hypothesis)
	gitHash := gitHash()

	if status == "reverted" {
		gitRevert()
		gitHash = gitHash()
	}

	return Experiment{
		ID:              expID,
		Hypothesis:      h.Hypothesis,
		Params:          h.Params,
		Metrics:         metrics,
		Score:           math.Round(score*10000) / 10000,
		Status:          status,
		Timestamp:       time.Now().UTC().Format(time.RFC3339),
		GitHash:         gitHash,
		DurationSeconds: math.Round(duration*10) / 10,
	}
}

func computeScore(metrics map[string]any, rubric Rubric) float64 {
	if metrics == nil {
		return 0
	}

	score := 0.0
	weightSum := 0.0

	for metric, weight := range rubric.Weights {
		val, ok := metrics[metric]
		if !ok {
			continue
		}
		fval, ok := toFloat64(val)
		if !ok {
			continue
		}
		weightSum += weight

		if metric == rubric.PrimaryMetric {
			score += weight * fval
		} else if metric == "inference_time_ms" {
			score += weight * (1.0 - fval/10.0)
		} else if metric == "loss" {
			score += weight * (1.0 - fval)
		} else {
			score += weight * fval
		}
	}

	if weightSum > 0 {
		score /= weightSum
	}

	return score
}

// ─── I/O ────────────────────────────────────────────────────────────────────

func readContext() string {
	data, err := os.ReadFile(filepath.Join(cfg.WorkDir, "context.md"))
	if err != nil {
		return "# Context\n\n## Goal\nNo goal set."
	}
	return string(data)
}

func loadResults() {
	data, err := os.ReadFile(filepath.Join(cfg.WorkDir, "results.json"))
	if err != nil {
		experiments = []Experiment{}
		return
	}
	json.Unmarshal(data, &experiments)

	// Find next ID and best score
	for _, e := range experiments {
		if e.Score > bestScore {
			bestScore = e.Score
		}
		parts := strings.Split(e.ID, "-")
		if len(parts) == 2 {
			if id, err := strconv.Atoi(parts[1]); err == nil && id >= nextExpID {
				nextExpID = id + 1
			}
		}
	}
}

func saveResults() {
	data, _ := json.MarshalIndent(experiments, "", "  ")
	os.WriteFile(filepath.Join(cfg.WorkDir, "results.json"), data, 0644)
}

func loadRubric() Rubric {
	r := Rubric{
		PrimaryMetric:  "f1_score",
		HigherIsBetter: true,
		Weights:        map[string]float64{"f1_score": 1.0},
		PassThreshold:  0.0,
		FailThreshold:  -0.05,
	}

	data, err := os.ReadFile(filepath.Join(cfg.WorkDir, cfg.RubricPath))
	if err != nil {
		return r
	}

	var loaded Rubric
	if err := json.Unmarshal(data, &loaded); err == nil {
		if loaded.PrimaryMetric != "" {
			r.PrimaryMetric = loaded.PrimaryMetric
		}
		r.HigherIsBetter = loaded.HigherIsBetter
		if len(loaded.Weights) > 0 {
			r.Weights = loaded.Weights
		}
		if loaded.PassThreshold != 0 {
			r.PassThreshold = loaded.PassThreshold
		}
		if loaded.FailThreshold != 0 {
			r.FailThreshold = loaded.FailThreshold
		}
	}

	return r
}

func summarizeResults() string {
	experimentsMu.RLock()
	defer experimentsMu.RUnlock()

	if len(experiments) == 0 {
		return "No past experiments."
	}

	var lines []string
	start := max(0, len(experiments)-10)
	for _, e := range experiments[start:] {
		hypo := e.Hypothesis
		if len(hypo) > 60 {
			hypo = hypo[:60]
		}
		lines = append(lines, fmt.Sprintf("  [%s] %s → score=%.4f (%s)", e.ID, hypo, e.Score, e.Status))
	}
	return strings.Join(lines, "\n")
}

// ─── Git Operations ─────────────────────────────────────────────────────────

func gitInit() {
	if _, err := os.Stat(filepath.Join(cfg.WorkDir, ".git")); os.IsNotExist(err) {
		execGit("init")
		execGit("config", "user.email", "autoclaw@local")
		execGit("config", "user.name", "Autoclaw Agent")
		execGit("add", "-A")
		execGit("commit", "-m", "Initial state")
	}
}

func gitCommit(expID, hypothesis string) {
	msg := fmt.Sprintf("[%s] %s", expID, hypothesis)
	if len(msg) > 80 {
		msg = msg[:80]
	}
	execGit("add", "-A")
	execGit("commit", "-m", msg)
}

func gitRevert() {
	execGit("revert", "--no-edit", "HEAD")
}

func gitTag(tag string) {
	execGit("tag", "-f", tag)
}

func gitHash() string {
	out, err := execGit("rev-parse", "--short", "HEAD")
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(out))
}

func execGit(args ...string) ([]byte, error) {
	cmd := exec.Command("git", args...)
	cmd.Dir = cfg.WorkDir
	return cmd.CombinedOutput()
}

// ─── SSE Broadcast ──────────────────────────────────────────────────────────

func broadcastSSE(e Experiment) {
	sseMu.Lock()
	defer sseMu.Unlock()
	for _, ch := range sseClients {
		select {
		case ch <- e:
		default:
		}
	}
}

// ─── HTTP Server ────────────────────────────────────────────────────────────

func startHTTPServer() {
	mux := http.NewServeMux()
	mux.HandleFunc("/", serveDashboard)
	mux.HandleFunc("/events", handleSSE)
	mux.HandleFunc("/api/results", handleResults)
	mux.HandleFunc("/api/status", handleStatus)
	mux.HandleFunc("/api/context", handleContext)
	mux.HandleFunc("/api/start", handleStart)
	mux.HandleFunc("/api/stop", handleStop)
	mux.HandleFunc("/api/reset", handleReset)

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.Port),
		Handler: mux,
	}

	if err := server.ListenAndServe(); err != nil {
		log.Printf("HTTP server error: %v", err)
	}
}

func serveDashboard(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html")
	dashboardPath := filepath.Join(cfg.WorkDir, "dashboard.html")
	if data, err := os.ReadFile(dashboardPath); err == nil {
		w.Write(data)
	} else {
		w.Write([]byte("<html><body><h1>Dashboard not found</h1></body></html>"))
	}
}

func handleSSE(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", 500)
		return
	}

	ch := make(chan Experiment, 10)
	sseMu.Lock()
	sseClients = append(sseClients, ch)
	sseMu.Unlock()

	// Send existing results
	experimentsMu.RLock()
	for _, e := range experiments {
		data, _ := json.Marshal(e)
		fmt.Fprintf(w, "data: %s\n\n", data)
		flusher.Flush()
	}
	experimentsMu.RUnlock()

	// Stream new results
	ctx := r.Context()
	for {
		select {
		case <-ctx.Done():
			sseMu.Lock()
			for i, c := range sseClients {
				if c == ch {
					sseClients = append(sseClients[:i], sseClients[i+1:]...)
					break
				}
			}
			sseMu.Unlock()
			return
		case e := <-ch:
			data, _ := json.Marshal(e)
			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()
		}
	}
}

func handleResults(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	experimentsMu.RLock()
	defer experimentsMu.RUnlock()
	json.NewEncoder(w).Encode(experiments)
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	experimentsMu.RLock()
	n := len(experiments)
	bs := bestScore
	experimentsMu.RUnlock()

	s := Status{
		Running:          running,
		TotalExperiments: n,
		BestScore:        bs,
		BudgetRemaining:  budgetRemaining,
		Uptime:           time.Since(loopStartTime).Seconds(),
	}
	json.NewEncoder(w).Encode(s)
}

func handleContext(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	switch r.Method {
	case "GET":
		w.Header().Set("Content-Type", "text/plain")
		data, _ := os.ReadFile(filepath.Join(cfg.WorkDir, "context.md"))
		w.Write(data)
	case "POST":
		body, _ := io.ReadAll(r.Body)
		os.WriteFile(filepath.Join(cfg.WorkDir, "context.md"), body, 0644)
		json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
	}
}

func handleStart(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	if !running {
		running = true
		budgetRemaining = float64(cfg.Budget)
		loopStartTime = time.Now()
		go mainLoop()
		json.NewEncoder(w).Encode(map[string]string{"status": "started"})
	} else {
		json.NewEncoder(w).Encode(map[string]string{"status": "already_running"})
	}
}

func handleStop(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	if running {
		close(stopCh)
		stopCh = make(chan struct{})
		running = false
	}
	json.NewEncoder(w).Encode(map[string]string{"status": "stopped"})
}

func handleReset(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	experimentsMu.Lock()
	experiments = []Experiment{}
	bestScore = 0
	nextExpID = 1
	budgetRemaining = float64(cfg.Budget)
	experimentsMu.Unlock()
	saveResults()
	json.NewEncoder(w).Encode(map[string]string{"status": "reset"})
}

// ─── Utilities ──────────────────────────────────────────────────────────────

func atoi(s string) int {
	n, _ := strconv.Atoi(s)
	return n
}

func toFloat64(v any) (float64, bool) {
	switch val := v.(type) {
	case float64:
		return val, true
	case float32:
		return float64(val), true
	case int:
		return float64(val), true
	case int64:
		return float64(val), true
	case json.Number:
		f, _ := val.Float64()
		return f, true
	default:
		return 0, false
	}
}

func randInt(max int) int {
	n, err := rand.Int(rand.Reader, big.NewInt(int64(max)))
	if err != nil {
		return 0
	}
	return int(n.Int64())
}
