export interface Experiment {
  id: string;
  hypothesis: string;
  params: Record<string, unknown>;
  metrics: Record<string, unknown>;
  score: number;
  status: "completed" | "reverted" | "failed";
  timestamp: string;
  git_hash: string;
  duration_seconds: number;
  budget_remaining?: number;
}

export interface Status {
  running: boolean;
  total_experiments: number;
  best_score: number;
  budget_remaining: number;
  uptime: number;
}

export interface Hypothesis {
  hypothesis: string;
  params: Record<string, unknown>;
}

export interface Rubric {
  primary_metric: string;
  higher_is_better: boolean;
  weights: Record<string, number>;
  pass_threshold: number;
  fail_threshold: number;
}
