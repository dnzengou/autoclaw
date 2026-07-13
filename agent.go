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
	Budget      int    // Total experiment budget in seconds
	Model       string // LLM model name
	Hypotheses  int    // Hypotheses per iteration
	Port        int    // Dashboard HTTP port
	RubricPath  string // Path to rubric JSON
	NoDashboard bool
	AutoStart   bool   // Start the loop immediately (headless deploys)
	WorkDir     string // Working directory
}

// ─── Data Model ─────────────────────────────────────────────────────────────

type Experiment struct {
	ID              string         `json:"id"`
	Hypothesis      string         `json:"hypothesis"`
	Params          map[string]any `json:"params"`
	Metrics         map[string]any `json:"metrics"`
	Score           float64        `json:"score"`
	Status          string         `json:"status"`
	Timestamp       string         `json:"timestamp"`
	GitHash         string         `json:"git_hash"`
	DurationSeconds float64        `json:"duration_seconds"`
	BudgetRemaining float64        `json:"budget_remaining,omitempty"`
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
	Running          bool    `json:"running"`
	TotalExperiments int     `json:"total_experiments"`
	BestScore        float64 `json:"best_score"`
	BudgetRemaining  float64 `json:"budget_remaining"`
	Uptime           float64 `json:"uptime"`
}

// ─── Global State ───────────────────────────────────────────────────────────

var (
	cfg           Config
	experiments   []Experiment
	experimentsMu sync.RWMutex
	bestScore     float64
	nextExpID     int

	// Loop lifecycle state, guarded by runMu.
	runMu           sync.Mutex
	budgetRemaining float64
	loopStartTime   time.Time
	running         bool
	stopCh          chan struct{}

	sseClients []chan Experiment
	sseMu      sync.Mutex

	evoEngine   *EvoEngine
	dealsEngine *DealsEngine
)

// ─── Loop lifecycle (race-safe) ─────────────────────────────────────────────

func startLoop() bool {
	runMu.Lock()
	defer runMu.Unlock()
	if running {
		return false
	}
	running = true
	budgetRemaining = float64(cfg.Budget)
	loopStartTime = time.Now()
	stopCh = make(chan struct{})
	go mainLoop(stopCh)
	return true
}

func stopLoop() {
	runMu.Lock()
	defer runMu.Unlock()
	if running {
		close(stopCh)
		running = false
	}
}

func isRunning() bool {
	runMu.Lock()
	defer runMu.Unlock()
	return running
}

func budgetLeft() float64 {
	runMu.Lock()
	defer runMu.Unlock()
	return budgetRemaining
}

func spendBudget(seconds float64) float64 {
	runMu.Lock()
	defer runMu.Unlock()
	budgetRemaining -= seconds
	return budgetRemaining
}

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
			if i+1 < len(os.Args) {
				cfg.Budget = atoi(os.Args[i+1])
				i++
			}
		case "--model":
			if i+1 < len(os.Args) {
				cfg.Model = os.Args[i+1]
				i++
			}
		case "--hypotheses":
			if i+1 < len(os.Args) {
				cfg.Hypotheses = atoi(os.Args[i+1])
				i++
			}
		case "--port":
			if i+1 < len(os.Args) {
				cfg.Port = atoi(os.Args[i+1])
				i++
			}
		case "--rubric":
			if i+1 < len(os.Args) {
				cfg.RubricPath = os.Args[i+1]
				i++
			}
		case "--no-dashboard":
			cfg.NoDashboard = true
		case "--auto-start":
			cfg.AutoStart = true
		case "--work-dir":
			if i+1 < len(os.Args) {
				cfg.WorkDir = os.Args[i+1]
				i++
			}
		}
	}

	// Ensure work dir exists
	os.MkdirAll(filepath.Join(cfg.WorkDir, "experiments"), 0755)

	// Load existing results
	loadResults()

	// Init git
	gitInit()

	// EvoMetaClaw + deals pipeline
	evoEngine = NewEvoEngine(cfg.WorkDir)
	dealsEngine = NewDealsEngine(cfg.WorkDir)

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

	if cfg.AutoStart {
		startLoop()
		log.Println("Loop auto-started (--auto-start).")
	}

	// Handle signals
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		log.Println("Shutting down...")
		stopLoop()
		os.Exit(0)
	}()

	// Interactive CLI
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		cmd := strings.TrimSpace(scanner.Text())
		switch cmd {
		case "start":
			if startLoop() {
				log.Println("Loop started.")
			} else {
				log.Println("Already running.")
			}
		case "stop":
			stopLoop()
			log.Println("Stop signal sent.")
		case "status":
			experimentsMu.RLock()
			n := len(experiments)
			bs := bestScore
			experimentsMu.RUnlock()
			log.Printf("Running: %v | Experiments: %d | Best: %.4f | Budget left: %.1fs",
				isRunning(), n, bs, budgetLeft())
		case "quit":
			log.Println("Shutting down.")
			os.Exit(0)
		}
	}

	// Stdin hit EOF (e.g. running in a container with no TTY). Keep serving
	// if the dashboard is up; otherwise there is nothing left to do.
	if !cfg.NoDashboard {
		log.Println("Stdin closed; continuing in server mode.")
		select {}
	}
}

// ─── Main Loop ──────────────────────────────────────────────────────────────

func mainLoop(stop chan struct{}) {
	defer func() {
		runMu.Lock()
		running = false
		runMu.Unlock()
	}()

	iteration := 0
	for {
		select {
		case <-stop:
			return
		default:
		}

		if budgetLeft() <= 0 {
			log.Printf("Budget exhausted")
			return
		}

		iteration++
		context := readContext()
		pastResults := summarizeResults()

		// EvoMetaClaw: pick the strategy genome guiding this iteration.
		genome := evoEngine.Select()
		log.Printf("Iteration %d — genome %s (%s, fitness %.2f)",
			iteration, genome.ID, genome.Niche, genome.Fitness)

		hypotheses := generateHypotheses(context, pastResults, genome.Strategy)
		if len(hypotheses) == 0 {
			log.Println("No hypotheses generated, stopping.")
			return
		}

		log.Printf("Generated %d hypotheses", len(hypotheses))

		// Run each hypothesis
		for _, h := range hypotheses {
			select {
			case <-stop:
				return
			default:
			}

			if budgetLeft() <= 0 {
				return
			}

			expStart := time.Now()
			result := runExperiment(h)
			elapsed := time.Since(expStart).Seconds()
			result.BudgetRemaining = spendBudget(elapsed)

			// Append to results
			experimentsMu.Lock()
			experiments = append(experiments, result)
			if result.Score > bestScore {
				bestScore = result.Score
				gitTag(fmt.Sprintf("best-%s", result.ID))
			}
			best := bestScore
			experimentsMu.Unlock()
			saveResults()
			broadcastSSE(result)

			// EvoMetaClaw: every outcome is a training signal.
			evoEngine.Record(genome.ID, result.ID, result.Hypothesis, result.Score, best)

			log.Printf("%s: score=%.4f, status=%s, budget_left=%.1fs",
				result.ID, result.Score, result.Status, result.BudgetRemaining)
		}

		time.Sleep(1 * time.Second)
	}
}

// ─── Hypothesis Generation ──────────────────────────────────────────────────

type Hypothesis struct {
	Hypothesis string         `json:"hypothesis"`
	Params     map[string]any `json:"params"`
}

func generateHypotheses(context, pastResults, strategy string) []Hypothesis {
	// Try LLM API first
	if key := os.Getenv("ANTHROPIC_API_KEY"); key != "" {
		if h := callAnthropic(key, context, pastResults, strategy); len(h) > 0 {
			return h
		}
	}
	if key := os.Getenv("DEEPSEEK_API_KEY"); key != "" {
		if h := callDeepSeek(key, context, pastResults, strategy); len(h) > 0 {
			return h
		}
	}
	if key := os.Getenv("OPENAI_API_KEY"); key != "" {
		if h := callOpenAI(key, context, pastResults, strategy); len(h) > 0 {
			return h
		}
	}

	// Fallback: heuristic generator
	return fallbackHypotheses()
}

// anthropicModel returns the Claude model to use; override with AUTOCLAW_MODEL.
func anthropicModel() string {
	if m := os.Getenv("AUTOCLAW_MODEL"); m != "" {
		return m
	}
	return "claude-opus-4-8"
}

func callDeepSeek(apiKey, context, pastResults, strategy string) []Hypothesis {
	prompt := buildPrompt(context, pastResults, strategy)
	body := map[string]any{
		"model": cfg.Model,
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
		"max_tokens":  2000,
		"temperature": 0.7,
	}
	return callLLMAPI("https://api.deepseek.com/chat/completions", apiKey, body, "deepseek")
}

func callAnthropic(apiKey, context, pastResults, strategy string) []Hypothesis {
	prompt := buildPrompt(context, pastResults, strategy)
	body := map[string]any{
		"model":      anthropicModel(),
		"max_tokens": 4000,
		"messages":   []map[string]string{{"role": "user", "content": prompt}},
	}
	return callLLMAPI("https://api.anthropic.com/v1/messages", apiKey, body, "anthropic")
}

func callOpenAI(apiKey, context, pastResults, strategy string) []Hypothesis {
	prompt := buildPrompt(context, pastResults, strategy)
	body := map[string]any{
		"model":      cfg.Model,
		"messages":   []map[string]string{{"role": "user", "content": prompt}},
		"max_tokens": 2000,
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

func buildPrompt(context, pastResults, strategy string) string {
	strategyBlock := ""
	if strategy != "" {
		strategyBlock = "\n## Strategy Directive (from EvoMetaClaw)\n" + strategy + "\n"
	}
	return fmt.Sprintf(`You are an AI research scientist running experiments to optimize a model.

## Context (human's goals and constraints)
%s

## Past Experiment Results
%s
%s
Generate %d distinct hypotheses for the next experiments.
Each hypothesis must include specific parameter changes.

Return ONLY a JSON array of objects with keys: "hypothesis" (string) and "params" (dict).
Example:
[
  {"hypothesis": "Increase learning rate to 3e-5 with cosine decay", "params": {"lr": 3e-5, "scheduler": "cosine", "batch_size": 16, "epochs": 3}}
]

Generate %d hypotheses now:`, context, pastResults, strategyBlock, cfg.Hypotheses, cfg.Hypotheses)
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
	experimentsMu.Lock()
	expID := fmt.Sprintf("exp-%03d", nextExpID)
	nextExpID++
	experimentsMu.Unlock()
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
			"f1_score":          0.82 + float64(randInt(5))/100,
			"accuracy":          0.83,
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
	experimentsMu.RLock()
	currentBest := bestScore
	experimentsMu.RUnlock()
	status := "completed"
	if score < currentBest+rubric.FailThreshold {
		status = "reverted"
	}

	// Git
	gitCommit(expID, h.Hypothesis)
	hash := gitHash()

	if status == "reverted" {
		gitRevert()
		hash = gitHash()
	}

	return Experiment{
		ID:              expID,
		Hypothesis:      h.Hypothesis,
		Params:          h.Params,
		Metrics:         metrics,
		Score:           math.Round(score*10000) / 10000,
		Status:          status,
		Timestamp:       time.Now().UTC().Format(time.RFC3339),
		GitHash:         hash,
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
	experimentsMu.RLock()
	data, _ := json.MarshalIndent(experiments, "", "  ")
	experimentsMu.RUnlock()
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

	// EvoMetaClaw
	mux.HandleFunc("/api/evo/status", handleEvoStatus)
	mux.HandleFunc("/api/evo/genomes", handleEvoGenomes)
	mux.HandleFunc("/api/evo/trajectories", handleEvoTrajectories)

	// Deals pipeline + toolbox catalog
	dealsEngine.RegisterRoutes(mux)
	mux.HandleFunc("/api/toolbox", handleToolbox)

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

	runMu.Lock()
	s := Status{
		Running:          running,
		TotalExperiments: n,
		BestScore:        bs,
		BudgetRemaining:  budgetRemaining,
	}
	if !loopStartTime.IsZero() {
		s.Uptime = time.Since(loopStartTime).Seconds()
	}
	runMu.Unlock()
	json.NewEncoder(w).Encode(s)
}

func handleEvoStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(evoEngine.Status())
}

func handleEvoGenomes(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(evoEngine.Genomes())
}

func handleEvoTrajectories(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(evoEngine.RecentTrajectories(100))
}

func handleToolbox(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(toolbox)
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
	if startLoop() {
		json.NewEncoder(w).Encode(map[string]string{"status": "started"})
	} else {
		json.NewEncoder(w).Encode(map[string]string{"status": "already_running"})
	}
}

func handleStop(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	stopLoop()
	json.NewEncoder(w).Encode(map[string]string{"status": "stopped"})
}

func handleReset(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	experimentsMu.Lock()
	experiments = []Experiment{}
	bestScore = 0
	nextExpID = 1
	experimentsMu.Unlock()
	runMu.Lock()
	budgetRemaining = float64(cfg.Budget)
	runMu.Unlock()
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
