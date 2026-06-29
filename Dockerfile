# Multi-stage: try Go agent (single binary, no system deps), fall back to Python.
# Rust build path lives in Dockerfile.rust for later when src/ compiles cleanly.

# Build stage — Go is fastest, smallest, and src is already in agent.go
FROM golang:1.22-alpine AS go-builder
WORKDIR /build
COPY agent.go ./
RUN go mod init autoclaw 2>/dev/null || true \
 && CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/autoclaw agent.go

# Runtime — small, just needs git for the loop's commit/revert
FROM alpine:3.20
RUN apk add --no-cache git ca-certificates curl python3
WORKDIR /app

COPY --from=go-builder /out/autoclaw /usr/local/bin/autoclaw
COPY agent.py eval.py train.py dashboard.html context.md rubric.json ./

ENV PORT=8080
EXPOSE 8080

# Build stage — Go agent (single binary, stdlib only).
# The Rust path lives in Dockerfile.rust for when `cargo build --release` is green.
FROM golang:1.22-alpine3.20 AS go-builder
WORKDIR /build

COPY agent.go ./
RUN go mod init github.com/dnzengou/autoclaw && \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o /out/autoclaw .

# Runtime stage
FROM alpine:3.20
RUN apk add --no-cache git ca-certificates curl python3 tini && \
    addgroup -S autoclaw && adduser -S autoclaw -G autoclaw

WORKDIR /app

COPY --from=go-builder /out/autoclaw /usr/local/bin/autoclaw
COPY agent.py eval.py train.py dashboard.html context.md rubric.json ./

RUN chown -R autoclaw:autoclaw /app
USER autoclaw

ENV PORT=8080 \
    AUTOCLAW_WORKSPACE=/app

EXPOSE 8080

ENTRYPOINT ["/sbin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/status > /dev/null || exit 1

# Default: run the Go binary (server + dashboard).
# Override CMD to use Python: docker run ... python3 agent.py
CMD ["autoclaw", "--port", "8080"]
