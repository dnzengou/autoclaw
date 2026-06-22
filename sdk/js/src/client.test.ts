import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { createServer, type Server } from "node:http";
import { AutoclawClient } from "./client.js";

const fakeStatus = {
  running: true,
  total_experiments: 3,
  best_score: 0.87,
  budget_remaining: 142.5,
  uptime: 200.0,
};

const fakeExperiments = [
  { id: "exp-001", hypothesis: "lr=2e-5", params: {}, metrics: {},
    score: 0.82, status: "completed", timestamp: "2026-06-18T10:00:00Z",
    git_hash: "abc", duration_seconds: 12 },
  { id: "exp-002", hypothesis: "lr=3e-5", params: {}, metrics: {},
    score: 0.87, status: "completed", timestamp: "2026-06-18T10:01:00Z",
    git_hash: "def", duration_seconds: 14 },
];

let server: Server;
let url: string;

beforeAll(async () => {
  server = createServer((req, res) => {
    res.setHeader("Content-Type", "application/json");
    if (req.method === "GET" && req.url === "/api/status")
      return res.end(JSON.stringify(fakeStatus));
    if (req.method === "GET" && req.url === "/api/results")
      return res.end(JSON.stringify(fakeExperiments));
    if (req.method === "GET" && req.url === "/api/context") {
      res.setHeader("Content-Type", "text/plain");
      return res.end("# MISSION\nTest.\n");
    }
    if (req.method === "POST" && ["/api/start","/api/stop","/api/reset"].includes(req.url!))
      return res.end(JSON.stringify({ status: req.url!.split("/").pop() }));
    if (req.method === "POST" && req.url === "/api/context")
      return res.end(JSON.stringify({ status: "updated" }));
    res.statusCode = 404; res.end();
  });
  await new Promise<void>(r => server.listen(0, "127.0.0.1", () => r()));
  const addr = server.address();
  url = typeof addr === "object" && addr ? `http://127.0.0.1:${addr.port}` : "";
});

afterAll(() => new Promise<void>(r => server.close(() => r())));

describe("AutoclawClient", () => {
  it("status round-trip", async () => {
    const c = new AutoclawClient({ baseUrl: url });
    const s = await c.status();
    expect(s.best_score).toBe(0.87);
    expect(s.running).toBe(true);
  });

  it("experiments typed", async () => {
    const c = new AutoclawClient({ baseUrl: url });
    const exps = await c.experiments();
    expect(exps).toHaveLength(2);
    expect(exps[1].score).toBe(0.87);
  });

  it("best picks highest", async () => {
    const c = new AutoclawClient({ baseUrl: url });
    const best = await c.best();
    expect(best?.id).toBe("exp-002");
  });

  it("context round-trip", async () => {
    const c = new AutoclawClient({ baseUrl: url });
    expect(await c.getContext()).toContain("MISSION");
    await c.setContext("# new\n");
  });

  it("lifecycle endpoints", async () => {
    const c = new AutoclawClient({ baseUrl: url });
    expect((await c.start()).status).toBe("start");
    expect((await c.stop()).status).toBe("stop");
    expect((await c.reset()).status).toBe("reset");
  });
});
