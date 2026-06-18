// Package autoclaw is the Go client for the Autoclaw server.
package autoclaw

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Client struct {
	BaseURL string
	HTTP    *http.Client
}

func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		HTTP:    &http.Client{Timeout: 30 * time.Second},
	}
}

// ─── REST ──────────────────────────────────────────────────────────────────

func (c *Client) Status(ctx context.Context) (*Status, error) {
	var s Status
	return &s, c.doJSON(ctx, "GET", "/api/status", nil, &s)
}

func (c *Client) Experiments(ctx context.Context) ([]Experiment, error) {
	var es []Experiment
	return es, c.doJSON(ctx, "GET", "/api/results", nil, &es)
}

func (c *Client) Best(ctx context.Context) (*Experiment, error) {
	es, err := c.Experiments(ctx)
	if err != nil || len(es) == 0 {
		return nil, err
	}
	best := es[0]
	for _, e := range es[1:] {
		if e.Score > best.Score {
			best = e
		}
	}
	return &best, nil
}

func (c *Client) GetContext(ctx context.Context) (string, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", c.BaseURL+"/api/context", nil)
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("get context: %d", resp.StatusCode)
	}
	b, err := io.ReadAll(resp.Body)
	return string(b), err
}

func (c *Client) SetContext(ctx context.Context, content string) error {
	req, _ := http.NewRequestWithContext(ctx, "POST", c.BaseURL+"/api/context", strings.NewReader(content))
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("set context: %d", resp.StatusCode)
	}
	return nil
}

func (c *Client) Start(ctx context.Context) error  { return c.doJSON(ctx, "POST", "/api/start", nil, nil) }
func (c *Client) Stop(ctx context.Context) error   { return c.doJSON(ctx, "POST", "/api/stop", nil, nil) }
func (c *Client) Reset(ctx context.Context) error  { return c.doJSON(ctx, "POST", "/api/reset", nil, nil) }

// ─── Streaming (SSE) ───────────────────────────────────────────────────────

// StreamExperiments pushes each incoming experiment onto out. Returns when ctx
// cancels or the server closes the stream.
func (c *Client) StreamExperiments(ctx context.Context, out chan<- Experiment) error {
	req, _ := http.NewRequestWithContext(ctx, "GET", c.BaseURL+"/events", nil)
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		var e Experiment
		if err := json.Unmarshal([]byte(line[6:]), &e); err != nil {
			continue
		}
		if e.ID == "" {
			continue
		}
		select {
		case out <- e:
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	return scanner.Err()
}

// ─── Internals ─────────────────────────────────────────────────────────────

func (c *Client) doJSON(ctx context.Context, method, path string, body, out any) error {
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reqBody = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, reqBody)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("%s %s: %d %s", method, path, resp.StatusCode, string(b))
	}
	if out != nil {
		return json.NewDecoder(resp.Body).Decode(out)
	}
	io.Copy(io.Discard, resp.Body)
	return nil
}
