// evo_skillops.go — EvoSkillOps: lifecycle operations on the EvoMetaClaw
// genome population.
//
// evo.go decides which strategy plays next and learns from outcomes. This file
// handles what happens to strategies over their lifetime:
//
//   - CROSSOVER: two proven genomes recombine into a hybrid child.
//   - PRUNE: evolved genomes that keep playing without ever winning retire
//     before the population cap forces a cull.
//   - SKILL PACKS: proven genomes export to a portable JSON pack and import
//     into another workspace (deduped by strategy hash), so learned strategy
//     transfers between experiments.
//   - LINEAGE: walk a genome's ancestry back to its gen-0 seed.
//
// Stdlib only. Methods without a lock suffix expect e.mu to be held.

package main

import (
	"fmt"
	"sort"
	"strings"
	"time"
)

const (
	evoCrossoverEvery = 5    // attempt crossover every N trajectories
	evoPruneMinPlays  = 6    // plays before a winless genome can be retired
	evoPruneFitness   = 0.35 // ...and only if its fitness fell below this
	evoImportFitness  = 0.55 // imported skills start slightly above neutral
	evoStrategyMax    = 280  // max runes kept in a derived strategy
	skillPackVersion  = 1
)

// SkillPack is the portable export format for proven genomes.
type SkillPack struct {
	Version    int           `json:"version"`
	ExportedAt string        `json:"exported_at"`
	Skills     []SkillGenome `json:"skills"`
}

// ImportResult reports what ImportSkills did with a pack.
type ImportResult struct {
	Imported int      `json:"imported"`
	Merged   int      `json:"merged"`  // duplicates whose memories were merged in
	Skipped  int      `json:"skipped"` // empty or duplicate with nothing new
	IDs      []string `json:"ids"`
}

// truncateRunes cuts s to at most n runes without splitting a UTF-8 sequence.
func truncateRunes(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}

// strategyKey identifies a strategy independent of whitespace and case, so
// imports and crossovers don't duplicate an existing direction.
func strategyKey(strategy string) string {
	return hashID(strings.ToLower(strings.Join(strings.Fields(strategy), " ")))
}

func (e *EvoEngine) findStrategy(strategy string) *SkillGenome {
	key := strategyKey(strategy)
	for i := range e.genomes {
		if strategyKey(e.genomes[i].Strategy) == key {
			return &e.genomes[i]
		}
	}
	return nil
}

func (e *EvoEngine) hasStrategy(strategy string) bool { return e.findStrategy(strategy) != nil }

// mergeMemories folds new memories into g, skipping hypotheses it already
// holds. Reports whether anything was added.
func mergeMemories(g *SkillGenome, mems []GenomeMemory) bool {
	added := false
	for _, m := range mems {
		dup := false
		for _, have := range g.Memories {
			if have.Hypothesis == m.Hypothesis {
				dup = true
				break
			}
		}
		if !dup {
			g.Memories = appendMemory(g.Memories, m)
			added = true
		}
	}
	return added
}

// crossover recombines the two fittest winning genomes from different niches
// into a hybrid. Returns false when no eligible pair exists or the hybrid
// would duplicate an existing strategy.
func (e *EvoEngine) crossover() bool {
	var winners []*SkillGenome
	for i := range e.genomes {
		if e.genomes[i].Wins > 0 {
			winners = append(winners, &e.genomes[i])
		}
	}
	sort.SliceStable(winners, func(i, j int) bool { return winners[i].Fitness > winners[j].Fitness })

	var a, b *SkillGenome
	for i := 0; i < len(winners) && b == nil; i++ {
		for j := i + 1; j < len(winners); j++ {
			if winners[i].Niche != winners[j].Niche {
				a, b = winners[i], winners[j]
				break
			}
		}
	}
	if a == nil {
		return false
	}

	strategy := truncateRunes(fmt.Sprintf("Combine two proven strategies in one experiment. A (%s): %s B (%s): %s",
		a.Name, a.Strategy, b.Name, b.Strategy), evoStrategyMax)
	if e.hasStrategy(strategy) {
		return false
	}

	gen := max(a.Generation, b.Generation) + 1
	e.nextGenomeID++
	e.generations = max(e.generations, gen)
	e.genomes = append(e.genomes, SkillGenome{
		ID:         fmt.Sprintf("evo-%04d", e.nextGenomeID),
		Name:       fmt.Sprintf("hybrid-%04d", e.nextGenomeID),
		Niche:      "hybrid",
		Strategy:   strategy,
		Fitness:    (a.Fitness + b.Fitness) / 2,
		Generation: gen,
		ParentID:   a.ID,
		ParentIDs:  []string{a.ID, b.ID},
		CreatedAt:  time.Now().UTC().Format(time.RFC3339),
	})
	return true
}

// prune retires evolved genomes that have had a fair number of plays, never
// won, and whose fitness decayed below the floor. Gen-0 seeds are kept so
// every niche stays reachable.
func (e *EvoEngine) prune() int {
	kept := e.genomes[:0]
	removed := 0
	for _, g := range e.genomes {
		if g.Generation > 0 && g.Plays >= evoPruneMinPlays && g.Wins == 0 && g.Fitness < evoPruneFitness {
			removed++
			continue
		}
		kept = append(kept, g)
	}
	e.genomes = kept
	e.retired += removed
	return removed
}

// ExportSkills returns every genome with at least minWins wins, best first.
func (e *EvoEngine) ExportSkills(minWins int) SkillPack {
	e.mu.Lock()
	defer e.mu.Unlock()
	pack := SkillPack{
		Version:    skillPackVersion,
		ExportedAt: time.Now().UTC().Format(time.RFC3339),
		Skills:     []SkillGenome{},
	}
	for _, g := range e.genomes {
		if g.Wins >= minWins {
			pack.Skills = append(pack.Skills, g)
		}
	}
	sort.SliceStable(pack.Skills, func(i, j int) bool { return pack.Skills[i].Fitness > pack.Skills[j].Fitness })
	return pack
}

// ImportSkills adds a pack's genomes under fresh IDs. Play statistics reset —
// a skill has to re-prove itself in this workspace — but memories carry over
// so the prompt still sees what worked before. A skill whose strategy already
// exists here (e.g. a shared gen-0 seed) merges its memories into that genome.
func (e *EvoEngine) ImportSkills(pack SkillPack) ImportResult {
	e.mu.Lock()
	defer e.mu.Unlock()
	res := ImportResult{IDs: []string{}}
	now := time.Now().UTC().Format(time.RFC3339)
	for _, s := range pack.Skills {
		if strings.TrimSpace(s.Strategy) == "" {
			res.Skipped++
			continue
		}
		if existing := e.findStrategy(s.Strategy); existing != nil {
			if mergeMemories(existing, s.Memories) {
				res.Merged++
			} else {
				res.Skipped++
			}
			continue
		}
		e.nextGenomeID++
		gen := max(1, s.Generation)
		e.generations = max(e.generations, gen)
		name := s.Name
		if name == "" {
			name = fmt.Sprintf("imported-%04d", e.nextGenomeID)
		}
		niche := s.Niche
		if niche == "" {
			niche = "imported"
		}
		g := SkillGenome{
			ID:         fmt.Sprintf("evo-%04d", e.nextGenomeID),
			Name:       name,
			Niche:      niche,
			Strategy:   truncateRunes(s.Strategy, evoStrategyMax),
			Fitness:    evoImportFitness,
			Generation: gen,
			ImportedID: s.ID,
			CreatedAt:  now,
			Memories:   s.Memories,
		}
		e.genomes = append(e.genomes, g)
		res.Imported++
		res.IDs = append(res.IDs, g.ID)
	}
	e.cull()
	e.save()
	return res
}

// Lineage returns the genome and its ancestors, newest first. Ancestors that
// were culled end the chain.
func (e *EvoEngine) Lineage(id string) []SkillGenome {
	e.mu.Lock()
	defer e.mu.Unlock()
	var chain []SkillGenome
	seen := map[string]bool{}
	for id != "" && !seen[id] {
		seen[id] = true
		g := e.find(id)
		if g == nil {
			break
		}
		chain = append(chain, *g)
		id = g.ParentID
	}
	return chain
}
