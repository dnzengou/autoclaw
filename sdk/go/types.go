package autoclaw

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

type Status struct {
	Running          bool    `json:"running"`
	TotalExperiments int     `json:"total_experiments"`
	BestScore        float64 `json:"best_score"`
	BudgetRemaining  float64 `json:"budget_remaining"`
	Uptime           float64 `json:"uptime"`
}

type Hypothesis struct {
	Hypothesis string         `json:"hypothesis"`
	Params     map[string]any `json:"params"`
}
