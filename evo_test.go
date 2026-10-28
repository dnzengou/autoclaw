package main

import (
	"strings"
	"testing"
	"unicode/utf8"
)

func newTestEngine(t *testing.T) *EvoEngine {
	t.Helper()
	return NewEvoEngine(t.TempDir())
}

func TestSeedAndSelect(t *testing.T) {
	e := newTestEngine(t)
	if n := len(e.Genomes()); n != 5 {
		t.Fatalf("seed population = %d, want 5", n)
	}
	for i := 0; i < 50; i++ {
		if g := e.Select(); e.find(g.ID) == nil {
			t.Fatalf("Select returned unknown genome %q", g.ID)
		}
	}
}

func TestRecordWinSpawnsGenomeWithMemory(t *testing.T) {
	e := newTestEngine(t)
	e.Record("gen0-00", "exp-001", "lr 3e-5 cosine", 0.8, 0)

	g := e.find("gen0-00")
	if g.Wins != 1 || len(g.Memories) != 1 {
		t.Fatalf("wins=%d memories=%d, want 1/1", g.Wins, len(g.Memories))
	}
	if n := len(e.Genomes()); n != 6 {
		t.Fatalf("population = %d, want 6 after a win", n)
	}
	if !strings.Contains(e.StrategyWithMemory(*g), "lr 3e-5 cosine") {
		t.Fatal("strategy prompt missing prior win")
	}

	// The same winning hypothesis must not spawn a duplicate genome.
	e.Record("gen0-00", "exp-002", "lr 3e-5 cosine", 0.9, 0.8)
	if n := len(e.Genomes()); n != 6 {
		t.Fatalf("population = %d, want 6 (duplicate strategy skipped)", n)
	}
}

func TestPriorBestIsNotAnImprovement(t *testing.T) {
	e := newTestEngine(t)
	// Fresh evo state, but the loop already reached 0.9 earlier.
	e.Record("gen0-01", "exp-010", "weight decay 0.1", 0.5, 0.9)
	if g := e.find("gen0-01"); g.Wins != 0 {
		t.Fatal("score below the loop's prior best counted as a win")
	}
}

func TestStagnationInjectsDiversity(t *testing.T) {
	e := newTestEngine(t)
	e.Record("gen0-00", "exp-000", "baseline", 0.9, 0)
	for i := 0; i < evoStagnationLimit; i++ {
		e.Record("gen0-01", "exp", "no gain", 0.1, 0.9)
	}
	found := false
	for _, g := range e.Genomes() {
		if g.Niche == "diversity" {
			found = true
		}
	}
	if !found {
		t.Fatal("no diversity genome after stagnation")
	}
}

func TestCrossoverCombinesNiches(t *testing.T) {
	e := newTestEngine(t)
	e.genomes[0].Wins, e.genomes[0].Fitness = 2, 0.8
	e.genomes[1].Wins, e.genomes[1].Fitness = 1, 0.7
	if !e.crossover() {
		t.Fatal("crossover returned false with two winning niches")
	}
	h := e.genomes[len(e.genomes)-1]
	if h.Niche != "hybrid" || len(h.ParentIDs) != 2 || h.Generation != 1 {
		t.Fatalf("bad hybrid: %+v", h)
	}
	if e.crossover() {
		t.Fatal("second identical crossover should be deduped")
	}
}

func TestPruneRetiresWinlessEvolvedOnly(t *testing.T) {
	e := newTestEngine(t)
	e.genomes[0].Plays, e.genomes[0].Fitness = 10, 0.1 // seed: kept
	e.genomes = append(e.genomes, SkillGenome{ID: "evo-9999", Generation: 1, Plays: 10, Fitness: 0.2})
	if n := e.prune(); n != 1 {
		t.Fatalf("pruned %d, want 1", n)
	}
	if e.find("gen0-00") == nil || e.find("evo-9999") != nil {
		t.Fatal("prune removed the wrong genome")
	}
	if e.Status().Retired != 1 {
		t.Fatal("retired counter not updated")
	}
}

func TestSkillPackRoundTrip(t *testing.T) {
	src := newTestEngine(t)
	src.Record("gen0-02", "exp-001", "pre-norm layers", 0.7, 0)
	if proven := src.ExportSkills(1); len(proven.Skills) != 1 || proven.Skills[0].ID != "gen0-02" {
		t.Fatalf("ExportSkills(1) = %+v, want only the winning seed", proven.Skills)
	}
	pack := src.ExportSkills(0)

	dst := newTestEngine(t)
	res := dst.ImportSkills(pack)
	// The learned genome is new; the winning seed merges its memory into the
	// matching local seed; the other four seeds have nothing new.
	if res.Imported != 1 || res.Merged != 1 || res.Skipped != 4 {
		t.Fatalf("import = %+v, want 1 imported / 1 merged / 4 skipped", res)
	}
	if len(dst.find("gen0-02").Memories) != 1 {
		t.Fatal("seed memory not merged")
	}
	for _, id := range res.IDs {
		g := dst.find(id)
		if g.Plays != 0 || g.Fitness != evoImportFitness || g.ImportedID == "" {
			t.Fatalf("imported genome not reset: %+v", g)
		}
	}
	if again := dst.ImportSkills(pack); again.Imported != 0 || again.Merged != 0 {
		t.Fatalf("re-import should be a no-op, got %+v", again)
	}

	// State survives a reload from disk.
	reloaded := NewEvoEngine(strings.TrimSuffix(dst.dir, "/.autoclaw/evo"))
	if len(reloaded.Genomes()) != len(dst.Genomes()) {
		t.Fatal("imported genomes not persisted")
	}
}

func TestLineage(t *testing.T) {
	e := newTestEngine(t)
	e.Record("gen0-00", "exp-001", "first win", 0.6, 0)
	child := e.genomes[len(e.genomes)-1]
	chain := e.Lineage(child.ID)
	if len(chain) != 2 || chain[1].ID != "gen0-00" {
		t.Fatalf("lineage = %+v", chain)
	}
}

func TestTruncateRunesKeepsUTF8(t *testing.T) {
	s := strings.Repeat("é", 200)
	out := truncateRunes(s, 141)
	if !utf8.ValidString(out) || utf8.RuneCountInString(out) != 141 {
		t.Fatalf("bad truncation: %d runes, valid=%v", utf8.RuneCountInString(out), utf8.ValidString(out))
	}
}
