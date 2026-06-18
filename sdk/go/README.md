# autoclaw — Go SDK

```bash
go get github.com/dnzengou/autoclaw/sdk/go
```

## Usage

```go
package main

import (
	"context"
	"fmt"
	autoclaw "github.com/dnzengou/autoclaw/sdk/go"
)

func main() {
	c := autoclaw.NewClient("http://localhost:8080")
	ctx := context.Background()

	c.Start(ctx)

	out := make(chan autoclaw.Experiment)
	go c.StreamExperiments(ctx, out)

	for e := range out {
		fmt.Printf("%s → %.4f (%s)\n", e.ID, e.Score, e.Status)
		if e.Score > 0.9 {
			c.Stop(ctx)
			return
		}
	}
}
```

MIT.
