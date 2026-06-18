import type { Experiment, Status } from "./types.js";

export interface ClientOptions {
  baseUrl?: string;
  fetch?: typeof fetch;
  timeout?: number;
}

export class AutoclawClient {
  readonly baseUrl: string;
  private readonly _fetch: typeof fetch;
  private readonly timeout: number;

  constructor(opts: ClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? "http://localhost:8080").replace(/\/$/, "");
    this._fetch = opts.fetch ?? fetch;
    this.timeout = opts.timeout ?? 30_000;
  }

  // ─── REST ──────────────────────────────────────────────────────────

  async status(): Promise<Status> {
    return this.get<Status>("/api/status");
  }

  async experiments(): Promise<Experiment[]> {
    return this.get<Experiment[]>("/api/results");
  }

  async best(): Promise<Experiment | null> {
    const exps = await this.experiments();
    return exps.length === 0
      ? null
      : exps.reduce((a, b) => (b.score > a.score ? b : a));
  }

  async getContext(): Promise<string> {
    const ctrl = this.abortAfter();
    const r = await this._fetch(`${this.baseUrl}/api/context`, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`get context: ${r.status}`);
    return r.text();
  }

  async setContext(content: string): Promise<void> {
    await this.post("/api/context", content);
  }

  async start(): Promise<{ status: string }> {
    return this.post<{ status: string }>("/api/start");
  }

  async stop(): Promise<{ status: string }> {
    return this.post<{ status: string }>("/api/stop");
  }

  async reset(): Promise<{ status: string }> {
    return this.post<{ status: string }>("/api/reset");
  }

  // ─── Streaming (SSE) ───────────────────────────────────────────────

  async *streamExperiments(signal?: AbortSignal): AsyncGenerator<Experiment> {
    const r = await this._fetch(`${this.baseUrl}/events`, { signal });
    if (!r.body) throw new Error("no response body");

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });

      let i: number;
      while ((i = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, i);
        buffer = buffer.slice(i + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data && typeof data.id === "string" && typeof data.score === "number") {
            yield data as Experiment;
          }
        } catch {
          // skip non-JSON lines (heartbeats etc.)
        }
      }
    }
  }

  // ─── WebSocket ─────────────────────────────────────────────────────

  streamWS(onEvent: (data: unknown) => void): () => void {
    const wsUrl = this.baseUrl.replace(/^http/, "ws") + "/ws";
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        onEvent(e.data);
      }
    };
    return () => ws.close();
  }

  // ─── Internals ─────────────────────────────────────────────────────

  private abortAfter(): AbortController {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), this.timeout);
    return ctrl;
  }

  private async get<T>(path: string): Promise<T> {
    const ctrl = this.abortAfter();
    const r = await this._fetch(`${this.baseUrl}${path}`, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
    return r.json() as Promise<T>;
  }

  private async post<T = unknown>(path: string, body?: string): Promise<T> {
    const ctrl = this.abortAfter();
    const r = await this._fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      body,
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`POST ${path}: ${r.status}`);
    return r.json() as Promise<T>;
  }
}
