# Build stage
FROM rust:1.75-slim-bookworm AS builder

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    libgit2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests (Cargo.lock not committed — cargo will generate inside the build)
COPY Cargo.toml ./

# Copy source
COPY src ./src

# Build release binary
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    git \
    libgit2-1.5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/target/release/autoclaw /usr/local/bin/autoclaw

# Create directories
RUN mkdir -p .autoclaw/metrics .autoclaw/logs .autoclaw/checkpoints

# Environment
ENV PORT=8080
ENV RUST_LOG=info
ENV AUTOCALW_WORKSPACE=/app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Default command
CMD ["autoclaw", "server", "--port", "8080"]
