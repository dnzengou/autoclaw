// evo.go — EvoMetaClaw: evolutionary strategy layer for the experiment loop.
//
// Every experiment becomes a training signal. Strategy genomes compete for
// selection; fitness updates from real outcomes; a circuit breaker injects
// diversity when the population stagnates; winning hypotheses are
// auto-summarized into new genomes. Trajectories accumulate on disk — that
// growing dataset is the flywheel a registry clone cannot copy.
//
// Stdlib only. State persists under .autoclaw/evo/.

package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// ─── Data Model ─────────────────────────────────────────────────────────────

type SkillGenome struct {
	ID         string  `json:"id"`
	Name       string  `json:"name"`
	Niche      string  `json:"niche"`
	Strategy   string  `json:"strategy"` // injected into the hypothesis prompt
	Fitness    float64 `json:"fitness"`
	Plays      int     `json:"plays"`
	Wins       int     `json:"wins"`
	Generation int     `json:"generation"`
	ParentID   string  `json:"parent_id,omitempty"`
	CreatedAt  string  `json:"created_at"`
}

type Trajectory struct {
	ExperimentID string  `json:"experiment_id"`
	GenomeID     string  `json:"genome_id"`
	Hypothesis   string  `json:"hypothesis"`
	Score        float64 `json:"score"`
	Delta        float64 `json:"delta"` // improvement over previous best
	Improved     bool    `json:"improved"`
	Timestamp    string  `json:"timestamp"`
}

type EvoStatus struct {
	PopulationSize  int          `json:"population_size"`
	TrajectoryCount int          `json:"trajectory_count"`
	Stagnation      int          `json:"stagnation"`
	BreakerTripped  bool         `json:"breaker_tripped"`
	BestGenome      *SkillGenome `json:"best_genome,omitempty"`
	Generations     int          `json:"generations"`
}

type EvoEngine struct {
	mu              sync.Mutex
	genomes         []SkillGenome
	dir             string
	trajectoryCount int
	stagnation      int
	generations     int
	lastBest        float64
	nextGenomeID    int
}

const (
	evoMaxPopulation   = 12
	evoStagnationLimit = 8   // experiments without improvement before diversity injection
	evoFitnessDecay    = 0.8 // EMA weight on prior fitness
	evoSelectionTemp   = 0.25
)

// Seed genomes: one per exploration niche. These are generation 0; everything
// else evolves from live trajectories.
func seedGenomes(now string) []SkillGenome {
	seeds := []struct{ name, niche, strategy string }{
		{"lr-tuner", "hyperparameters",
			"Focus on learning rate, warmup, and schedule changes. One knob per experiment."},
		{"regularizer", "regularization",
			"Focus on dropout, weight decay, label smoothing, or augmentation to reduce overfitting."},
		{"architect", "architecture",
			"Propose a structural change: layer sizes, normalization placement, activation choice."},
		{"data-shaper", "data",
			"Focus on data: batch composition, sampling, augmentation, or preprocessing changes."},
		{"radical", "exploration",
			"Propose a bold, unconventional change unlike previous experiments. High risk, high reward."},
	}
	genomes := make([]SkillGenome, len(seeds))
	for i, s := range seeds {
		genomes[i] = SkillGenome{
			ID:        fmt.Sprintf("gen0-%02d", i),
			Name:      s.name,
			Niche:     s.niche,
			Strategy:  s.strategy,
			Fitness:   0.5,
			CreatedAt: now,
		}
	}
	return genomes
}

// ─── Engine ─────────────────────────────────────────────────────────────────

func NewEvoEngine(workDir string) *EvoEngine {
	e := &EvoEngine{dir: filepath.Join(workDir, ".autoclaw", "evo")}
	os.MkdirAll(e.dir, 0755)
	e.load()
	if len(e.genomes) == 0 {
		e.genomes = seedGenomes(time.Now().UTC().Format(time.RFC3339))
		e.save()
	}
	return e
}

func (e *EvoEngine) genomesPath() string    { return filepath.Join(e.dir, "genomes.json") }
func (e *EvoEngine) trajectoryPath() string { return filepath.Join(e.dir, "trajectories.jsonl") }

func (e *EvoEngine) load() {
	if data, err := os.ReadFile(e.genomesPath()); err == nil {
		var state struct {
			Genomes         []SkillGenome `json:"genomes"`
			TrajectoryCount int           `json:"trajectory_count"`
			Stagnation      int           `json:"stagnation"`
			Generations     int           `json:"generations"`
			LastBest        float64       `json:"last_best"`
			NextGenomeID    int           `json:"next_genome_id"`
		}
		if json.Unmarshal(data, &state) == nil {
			e.genomes = state.Genomes
			e.trajectoryCount = state.TrajectoryCount
			e.stagnation = state.Stagnation
			e.generations = state.Generations
			e.lastBest = state.LastBest
			e.nextGenomeID = state.NextGenomeID
		}
	}
}

func (e *EvoEngine) save() {
	state := map[string]any{
		"genomes":          e.genomes,
		"trajectory_count": e.trajectoryCount,
		"stagnation":       e.stagnation,
		"generations":      e.generations,
		"last_best":        e.lastBest,
		"next_genome_id":   e.nextGenomeID,
	}
	if data, err := json.MarshalIndent(state, "", "  "); err == nil {
		os.WriteFile(e.genomesPath(), data, 0644)
	}
}

// Select picks a genome via softmax over fitness: better strategies get
// chosen more often, but every genome keeps a nonzero chance (exploration).
func (e *EvoEngine) Select() SkillGenome {
	e.mu.Lock()
	defer e.mu.Unlock()

	weights := make([]float64, len(e.genomes))
	total := 0.0
	for i, g := range e.genomes {
		weights[i] = math.Exp(g.Fitness / evoSelectionTemp)
		total += weights[i]
	}

	// randInt gives [0, 1e9); scale to total weight.
	r := float64(randInt(1_000_000_000)) / 1_000_000_000.0 * total
	for i, w := range weights {
		r -= w
		if r <= 0 {
			return e.genomes[i]
		}
	}
	return e.genomes[len(e.genomes)-1]
}

// Record feeds one experiment outcome back into the population and appends
// the trajectory to the on-disk log.
func (e *EvoEngine) Record(genomeID, experimentID, hypothesis string, score, bestScore float64) {
	e.mu.Lock()
	defer e.mu.Unlock()

	improved := score > e.lastBest
	delta := score - e.lastBest
	if improved {
		e.lastBest = score
		e.stagnation = 0
	} else {
		e.stagnation++
	}
	if bestScore > e.lastBest {
		e.lastBest = bestScore
	}

	// Reward in [0,1]: improvements score high, harmless failures low-mid.
	reward := 0.3
	if improved {
		reward = math.Min(1.0, 0.7+delta*10)
	}

	for i := range e.genomes {
		if e.genomes[i].ID == genomeID {
			g := &e.genomes[i]
			g.Plays++
			if improved {
				g.Wins++
			}
			g.Fitness = evoFitnessDecay*g.Fitness + (1-evoFitnessDecay)*reward
			break
		}
	}

	traj := Trajectory{
		ExperimentID: experimentID,
		GenomeID:     genomeID,
		Hypothesis:   hypothesis,
		Score:        score,
		Delta:        delta,
		Improved:     improved,
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
	}
	if line, err := json.Marshal(traj); err == nil {
		f, err := os.OpenFile(e.trajectoryPath(), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err == nil {
			f.Write(append(line, '\n'))
			f.Close()
		}
	}
	e.trajectoryCount++

	// AUTO_SKILL_SUMMARIZE: a winning hypothesis becomes a new genome so the
	// population accumulates proven directions.
	if improved && delta > 0 {
		e.spawnFromWin(genomeID, hypothesis)
	}

	// CIRCUIT_BREAKER: stagnation triggers diversity injection.
	if e.stagnation >= evoStagnationLimit {
		e.injectDiversity()
		e.stagnation = 0
	}

	e.cull()
	e.save()
}

func (e *EvoEngine) spawnFromWin(parentID, hypothesis string) {
	parent := e.find(parentID)
	gen := 1
	niche := "learned"
	if parent != nil {
		gen = parent.Generation + 1
		niche = parent.Niche
	}
	e.nextGenomeID++
	e.generations = max(e.generations, gen)
	summary := hypothesis
	if len(summary) > 140 {
		summary = summary[:140]
	}
	e.genomes = append(e.genomes, SkillGenome{
		ID:         fmt.Sprintf("evo-%04d", e.nextGenomeID),
		Name:       fmt.Sprintf("learned-%04d", e.nextGenomeID),
		Niche:      niche,
		Strategy:   "Build on this proven direction from a past winning experiment: " + summary,
		Fitness:    0.65, // head start: it just won
		Generation: gen,
		ParentID:   parentID,
		CreatedAt:  time.Now().UTC().Format(time.RFC3339),
	})
}

var diversityMutations = []string{
	"Combine two previously separate approaches into one experiment.",
	"Invert the last failed change: if something was increased, decrease it sharply.",
	"Question a base assumption in the context and design an experiment to test it.",
	"Simplify: remove complexity from the current setup instead of adding it.",
}

func (e *EvoEngine) injectDiversity() {
	best := e.best()
	parentID := ""
	gen := 1
	if best != nil {
		parentID = best.ID
		gen = best.Generation + 1
	}
	e.nextGenomeID++
	e.generations = max(e.generations, gen)
	mutation := diversityMutations[randInt(len(diversityMutations))]
	e.genomes = append(e.genomes, SkillGenome{
		ID:         fmt.Sprintf("evo-%04d", e.nextGenomeID),
		Name:       fmt.Sprintf("mutant-%04d", e.nextGenomeID),
		Niche:      "diversity",
		Strategy:   mutation,
		Fitness:    0.6, // above average so it actually gets played
		Generation: gen,
		ParentID:   parentID,
		CreatedAt:  time.Now().UTC().Format(time.RFC3339),
	})
}

// cull keeps the population bounded: gen-0 seeds are never removed, the
// weakest evolved genomes go first.
func (e *EvoEngine) cull() {
	for len(e.genomes) > evoMaxPopulation {
		worstIdx := -1
		for i, g := range e.genomes {
			if g.Generation == 0 {
				continue
			}
			if worstIdx == -1 || g.Fitness < e.genomes[worstIdx].Fitness {
				worstIdx = i
			}
		}
		if worstIdx == -1 {
			return
		}
		e.genomes = append(e.genomes[:worstIdx], e.genomes[worstIdx+1:]...)
	}
}

func (e *EvoEngine) find(id string) *SkillGenome {
	for i := range e.genomes {
		if e.genomes[i].ID == id {
			return &e.genomes[i]
		}
	}
	return nil
}

func (e *EvoEngine) best() *SkillGenome {
	var best *SkillGenome
	for i := range e.genomes {
		if best == nil || e.genomes[i].Fitness > best.Fitness {
			best = &e.genomes[i]
		}
	}
	return best
}

// ─── Read API ───────────────────────────────────────────────────────────────

func (e *EvoEngine) Genomes() []SkillGenome {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]SkillGenome, len(e.genomes))
	copy(out, e.genomes)
	return out
}

func (e *EvoEngine) Status() EvoStatus {
	e.mu.Lock()
	defer e.mu.Unlock()
	status := EvoStatus{
		PopulationSize:  len(e.genomes),
		TrajectoryCount: e.trajectoryCount,
		Stagnation:      e.stagnation,
		BreakerTripped:  e.stagnation >= evoStagnationLimit-1,
		Generations:     e.generations,
	}
	if b := e.best(); b != nil {
		c := *b
		status.BestGenome = &c
	}
	return status
}

// RecentTrajectories returns up to limit most recent trajectory records.
func (e *EvoEngine) RecentTrajectories(limit int) []Trajectory {
	e.mu.Lock()
	path := e.trajectoryPath()
	e.mu.Unlock()

	data, err := os.ReadFile(path)
	if err != nil {
		return []Trajectory{}
	}
	var all []Trajectory
	start := 0
	for i := 0; i <= len(data); i++ {
		if i == len(data) || data[i] == '\n' {
			if i > start {
				var t Trajectory
				if json.Unmarshal(data[start:i], &t) == nil {
					all = append(all, t)
				}
			}
			start = i + 1
		}
	}
	if len(all) > limit {
		all = all[len(all)-limit:]
	}
	return all
}

// hashID builds a stable short id from arbitrary strings (used for dedupe).
func hashID(parts ...string) string {
	h := sha256.New()
	for _, p := range parts {
		h.Write([]byte(p))
	}
	return hex.EncodeToString(h.Sum(nil))[:12]
}
