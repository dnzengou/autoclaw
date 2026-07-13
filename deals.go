// deals.go — customer prospect pipeline: intake → qualify → propose →
// human approval → deliver → get paid.
//
// Safety model: nothing leaves the system automatically. Intake happens via
// webhook POST, manual entry, or an explicit operator-triggered fetch from a
// configured feed URL (AUTOCLAW_DEALS_FEED). Every outbound step (proposal,
// delivery, payment) requires a human approval transition first.
//
// Stdlib only. State persists in .autoclaw/deals.json.

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// ─── Toolbox Catalog ────────────────────────────────────────────────────────

// ToolboxItem is a deliverable service from the desiredsolutions toolbox.
type ToolboxItem struct {
	Name        string   `json:"name"`
	Description string   `json:"description"`
	Keywords    []string `json:"keywords"`
	BasePrice   float64  `json:"base_price_usd"`
}

var toolbox = []ToolboxItem{
	{
		Name:        "Clow",
		Description: "Self-improving AI agent deployment and automation loops",
		Keywords:    []string{"agent", "automation", "ai loop", "autonomous", "bot", "claw", "self-improving"},
		BasePrice:   2500,
	},
	{
		Name:        "SAI Agency",
		Description: "AI strategy, consulting and custom AI solution delivery",
		Keywords:    []string{"consulting", "strategy", "ai solution", "advisory", "integration", "llm"},
		BasePrice:   3500,
	},
	{
		Name:        "MOOC Studio",
		Description: "Course design, e-learning production and MOOC platforms",
		Keywords:    []string{"course", "mooc", "training", "e-learning", "education", "curriculum", "workshop"},
		BasePrice:   1800,
	},
	{
		Name:        "ProductizeYou",
		Description: "Turning expertise into scalable digital products",
		Keywords:    []string{"productize", "digital product", "saas", "template", "package", "monetize"},
		BasePrice:   1500,
	},
	{
		Name:        "Funding Dashboard",
		Description: "Grant and funding discovery, tracking and application support",
		Keywords:    []string{"grant", "funding", "investor", "fundraising", "subsidy", "application"},
		BasePrice:   1200,
	},
	{
		Name:        "CAS Lab",
		Description: "Complex-adaptive-systems modeling, simulations and scientific webapps",
		Keywords:    []string{"simulation", "model", "modeling", "complex system", "digital twin", "scientific", "webapp", "dashboard"},
		BasePrice:   4000,
	},
}

// ─── Data Model ─────────────────────────────────────────────────────────────

// Deal statuses, in lifecycle order.
const (
	DealNew       = "new"
	DealQualified = "qualified" // matched to toolbox, proposal drafted
	DealApproved  = "approved"  // human approved → work may start
	DealRejected  = "rejected"
	DealDelivered = "delivered"
	DealPaid      = "paid"
)

type Deal struct {
	ID           string   `json:"id"`
	Source       string   `json:"source"` // manual | webhook | feed
	Customer     string   `json:"customer"`
	Contact      string   `json:"contact,omitempty"`
	Request      string   `json:"request"`
	MatchedTools []string `json:"matched_tools"`
	Proposal     string   `json:"proposal,omitempty"`
	PriceUSD     float64  `json:"price_usd"`
	Status       string   `json:"status"`
	PaymentLink  string   `json:"payment_link,omitempty"`
	CreatedAt    string   `json:"created_at"`
	UpdatedAt    string   `json:"updated_at"`
}

type DealsEngine struct {
	mu    sync.Mutex
	deals []Deal
	path  string
}

func NewDealsEngine(workDir string) *DealsEngine {
	d := &DealsEngine{path: filepath.Join(workDir, ".autoclaw", "deals.json")}
	os.MkdirAll(filepath.Dir(d.path), 0755)
	if data, err := os.ReadFile(d.path); err == nil {
		json.Unmarshal(data, &d.deals)
	}
	return d
}

func (d *DealsEngine) save() {
	if data, err := json.MarshalIndent(d.deals, "", "  "); err == nil {
		os.WriteFile(d.path, data, 0644)
	}
}

// ─── Pipeline ───────────────────────────────────────────────────────────────

// Intake registers a prospect request and immediately qualifies it against
// the toolbox. Duplicate customer+request pairs are ignored.
func (d *DealsEngine) Intake(source, customer, contact, request string) (*Deal, error) {
	customer = strings.TrimSpace(customer)
	request = strings.TrimSpace(request)
	if customer == "" || request == "" {
		return nil, fmt.Errorf("customer and request are required")
	}

	id := hashID(customer, request)

	d.mu.Lock()
	defer d.mu.Unlock()

	for i := range d.deals {
		if d.deals[i].ID == id {
			return &d.deals[i], fmt.Errorf("duplicate: deal %s already exists", id)
		}
	}

	now := time.Now().UTC().Format(time.RFC3339)
	deal := Deal{
		ID:        id,
		Source:    source,
		Customer:  customer,
		Contact:   strings.TrimSpace(contact),
		Request:   request,
		Status:    DealNew,
		CreatedAt: now,
		UpdatedAt: now,
	}

	deal.MatchedTools, deal.PriceUSD = matchToolbox(request)
	if len(deal.MatchedTools) > 0 {
		deal.Proposal = draftProposal(&deal)
		deal.Status = DealQualified
	}

	d.deals = append(d.deals, deal)
	d.save()
	return &d.deals[len(d.deals)-1], nil
}

// matchToolbox scores each toolbox item by keyword hits in the request.
func matchToolbox(request string) ([]string, float64) {
	lower := strings.ToLower(request)
	var matched []string
	price := 0.0
	for _, item := range toolbox {
		for _, kw := range item.Keywords {
			if strings.Contains(lower, kw) {
				matched = append(matched, item.Name)
				price += item.BasePrice
				break
			}
		}
	}
	return matched, price
}

func draftProposal(deal *Deal) string {
	var services []string
	for _, name := range deal.MatchedTools {
		for _, item := range toolbox {
			if item.Name == name {
				services = append(services, fmt.Sprintf("- %s: %s", item.Name, item.Description))
			}
		}
	}
	return fmt.Sprintf(
		"Proposal for %s\n\nRequest: %s\n\nProposed services:\n%s\n\nEstimated engagement: $%.0f USD.\nDelivery starts on approval; payment on delivery.",
		deal.Customer, deal.Request, strings.Join(services, "\n"), deal.PriceUSD,
	)
}

// Transition moves a deal through the human-gated lifecycle.
func (d *DealsEngine) Transition(id, action string) (*Deal, error) {
	d.mu.Lock()
	defer d.mu.Unlock()

	var deal *Deal
	for i := range d.deals {
		if d.deals[i].ID == id {
			deal = &d.deals[i]
			break
		}
	}
	if deal == nil {
		return nil, fmt.Errorf("deal %s not found", id)
	}

	// action → (allowed current statuses, next status)
	switch action {
	case "approve":
		if deal.Status != DealQualified && deal.Status != DealNew {
			return nil, fmt.Errorf("can only approve new/qualified deals (is: %s)", deal.Status)
		}
		deal.Status = DealApproved
		if link := os.Getenv("PAYMENT_LINK_URL"); link != "" {
			deal.PaymentLink = link
		}
	case "reject":
		if deal.Status == DealPaid {
			return nil, fmt.Errorf("cannot reject a paid deal")
		}
		deal.Status = DealRejected
	case "delivered":
		if deal.Status != DealApproved {
			return nil, fmt.Errorf("deal must be approved before delivery (is: %s)", deal.Status)
		}
		deal.Status = DealDelivered
	case "paid":
		if deal.Status != DealDelivered {
			return nil, fmt.Errorf("deal must be delivered before payment (is: %s)", deal.Status)
		}
		deal.Status = DealPaid
	default:
		return nil, fmt.Errorf("unknown action %q", action)
	}

	deal.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	d.save()
	return deal, nil
}

func (d *DealsEngine) List() []Deal {
	d.mu.Lock()
	defer d.mu.Unlock()
	out := make([]Deal, len(d.deals))
	copy(out, d.deals)
	return out
}

// FetchFeed pulls prospect requests from the operator-configured feed URL.
// Only runs when explicitly triggered; expects a JSON array of
// {customer, contact, request} objects.
func (d *DealsEngine) FetchFeed() (int, error) {
	feedURL := os.Getenv("AUTOCLAW_DEALS_FEED")
	if feedURL == "" {
		return 0, fmt.Errorf("AUTOCLAW_DEALS_FEED not configured")
	}

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Get(feedURL)
	if err != nil {
		return 0, fmt.Errorf("feed fetch failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return 0, fmt.Errorf("feed returned %d", resp.StatusCode)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20)) // 1 MiB cap
	if err != nil {
		return 0, err
	}

	var items []struct {
		Customer string `json:"customer"`
		Contact  string `json:"contact"`
		Request  string `json:"request"`
	}
	if err := json.Unmarshal(body, &items); err != nil {
		return 0, fmt.Errorf("feed is not a JSON array of prospects: %w", err)
	}

	added := 0
	for _, item := range items {
		if _, err := d.Intake("feed", item.Customer, item.Contact, item.Request); err == nil {
			added++
		}
	}
	return added, nil
}

// ─── HTTP Handlers ──────────────────────────────────────────────────────────

func (d *DealsEngine) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/deals", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		switch r.Method {
		case http.MethodGet:
			json.NewEncoder(w).Encode(d.List())
		case http.MethodPost:
			var req struct {
				Customer string `json:"customer"`
				Contact  string `json:"contact"`
				Request  string `json:"request"`
				Source   string `json:"source"`
			}
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				httpError(w, 400, "invalid JSON body")
				return
			}
			source := req.Source
			if source == "" {
				source = "manual"
			}
			deal, err := d.Intake(source, req.Customer, req.Contact, req.Request)
			if err != nil {
				httpError(w, 409, err.Error())
				return
			}
			json.NewEncoder(w).Encode(deal)
		default:
			httpError(w, 405, "method not allowed")
		}
	})

	mux.HandleFunc("/api/deals/fetch", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		if r.Method != http.MethodPost {
			httpError(w, 405, "method not allowed")
			return
		}
		added, err := d.FetchFeed()
		if err != nil {
			httpError(w, 502, err.Error())
			return
		}
		json.NewEncoder(w).Encode(map[string]int{"added": added})
	})

	// POST /api/deals/{id}/{action} — approval-gated transitions.
	mux.HandleFunc("/api/deals/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		if r.Method != http.MethodPost {
			httpError(w, 405, "method not allowed")
			return
		}
		parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/deals/"), "/")
		if len(parts) != 2 {
			httpError(w, 400, "expected /api/deals/{id}/{action}")
			return
		}
		deal, err := d.Transition(parts[0], parts[1])
		if err != nil {
			httpError(w, 409, err.Error())
			return
		}
		json.NewEncoder(w).Encode(deal)
	})
}

func httpError(w http.ResponseWriter, code int, msg string) {
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
