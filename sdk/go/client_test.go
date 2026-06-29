package autoclaw

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func fakeServer(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/api/status", func(w http.ResponseWriter, _ *http.Request) {
		json.NewEncoder(w).Encode(Status{Running: true, TotalExperiments: 3, BestScore: 0.87, BudgetRemaining: 142.5, Uptime: 200})
	})
	mux.HandleFunc("/api/results", func(w http.ResponseWriter, _ *http.Request) {
		json.NewEncoder(w).Encode([]Experiment{
			{ID: "exp-001", Hypothesis: "lr=2e-5", Score: 0.82, Status: "completed"},
			{ID: "exp-002", Hypothesis: "lr=3e-5", Score: 0.87, Status: "completed"},
		})
	})
	mux.HandleFunc("/api/context", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			w.Header().Set("Content-Type", "text/plain")
			w.Write([]byte("# MISSION\nTest.\n"))
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "updated"})
	})
	for _, p := range []string{"/api/start", "/api/stop", "/api/reset"} {
		path := p
		mux.HandleFunc(path, func(w http.ResponseWriter, _ *http.Request) {
			json.NewEncoder(w).Encode(map[string]string{"status": strings.TrimPrefix(path, "/api/")})
		})
	}
	return httptest.NewServer(mux)
}

func TestStatus(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()
	c := NewClient(srv.URL)
	s, err := c.Status(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if s.BestScore != 0.87 {
		t.Errorf("BestScore = %v, want 0.87", s.BestScore)
	}
	if !s.Running {
		t.Error("expected Running=true")
	}
}

func TestExperiments(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()
	c := NewClient(srv.URL)
	es, err := c.Experiments(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(es) != 2 {
		t.Fatalf("len = %d, want 2", len(es))
	}
	if es[1].Score != 0.87 {
		t.Errorf("es[1].Score = %v, want 0.87", es[1].Score)
	}
}

func TestBest(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()
	c := NewClient(srv.URL)
	best, err := c.Best(context.Background())
	if err != nil || best == nil {
		t.Fatalf("Best returned err=%v, best=%v", err, best)
	}
	if best.ID != "exp-002" {
		t.Errorf("best.ID = %q, want exp-002", best.ID)
	}
}

func TestContextRoundTrip(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()
	c := NewClient(srv.URL)
	text, err := c.GetContext(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(text, "MISSION") {
		t.Errorf("context missing MISSION: %q", text)
	}
	if err := c.SetContext(context.Background(), "# new\n"); err != nil {
		t.Errorf("SetContext: %v", err)
	}
}

func TestLifecycle(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()
	c := NewClient(srv.URL)
	ctx := context.Background()
	for _, fn := range []func(context.Context) error{c.Start, c.Stop, c.Reset} {
		if err := fn(ctx); err != nil {
			t.Errorf("lifecycle: %v", err)
		}
	}
}
