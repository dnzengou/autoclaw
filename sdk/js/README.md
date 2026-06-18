# @autoclaw/sdk

```bash
npm i @autoclaw/sdk
```

## Usage

```ts
import { AutoclawClient } from "@autoclaw/sdk";

const c = new AutoclawClient({ baseUrl: "http://localhost:8080" });

await c.start();
for await (const exp of c.streamExperiments()) {
  console.log(`${exp.id} → ${exp.score.toFixed(4)} (${exp.status})`);
  if (exp.score > 0.9) {
    await c.stop();
    break;
  }
}
```

Works in: Node 18+, Deno, Bun, modern browsers (with CORS).

MIT.
