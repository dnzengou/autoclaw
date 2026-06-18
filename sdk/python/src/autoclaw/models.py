"""Typed data models mirroring the Autoclaw server JSON schema."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    hypothesis: str
    params: dict[str, Any] = Field(default_factory=dict)


class Experiment(BaseModel):
    id: str
    hypothesis: str
    params: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    score: float
    status: str
    timestamp: str
    git_hash: str = ""
    duration_seconds: float = 0.0
    budget_remaining: float | None = None


class Rubric(BaseModel):
    primary_metric: str = "f1_score"
    higher_is_better: bool = True
    weights: dict[str, float] = Field(default_factory=lambda: {"f1_score": 1.0})
    pass_threshold: float = 0.0
    fail_threshold: float = -0.05


class Status(BaseModel):
    running: bool
    total_experiments: int
    best_score: float
    budget_remaining: float
    uptime: float
