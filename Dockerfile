# Build stage — Go agent (single binary, no system deps, ~20s build).
# The Rust path lives in Dockerfile.rust for when `cargo build --release` is green.
FROM golang:1.22-alpine3.20 AS go-builder
WORKDIR /build

# Module init BEFORE copying source — stable cache layer for stdlib-only build.
RUN go env -w GOFLAGS='-mod=mod' && \
    printf 'module github.com/dnzengou/autoclaw\n\ngo 1.22\n' > go.mod

COPY agent.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o /out/autoclaw agent.go

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

# tini = PID 1 reaper for clean signal handling
ENTRYPOINT ["/sbin/tini", "--"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/status > /dev/null || exit 1

# Default: Go binary. Override CMD with `python3 agent.py` for the Python path.
CMD ["autoclaw", "--port", "8080"]
