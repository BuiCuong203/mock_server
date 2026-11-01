# Dockerfile for Cloud Mock Server
# -------------------------------------------------
# Stage 1: build mock GCP Pub/Sub (Go, pstest) thành binary tĩnh
FROM golang:1.25 AS pubsub-builder
WORKDIR /src
COPY pubsub_mock/go.mod pubsub_mock/go.sum ./
RUN go mod download
COPY pubsub_mock/*.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/pubsub_mock .

# Stage 2: Cloud Mock Server (Python), chạy kèm pubsub_mock
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install any Python dependencies if a requirements file exists.
# The project currently does not ship a requirements.txt, but this command
# is safe to run – it will simply be a no‑op when the file is missing.
# Install dependencies (openssl cần cho cert_manager sinh SSL cert tự động)
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt – skipping pip install"; \
    fi

# Copy toàn bộ source code
COPY . .
COPY --from=pubsub-builder /out/pubsub_mock /app/bin/pubsub_mock
RUN sed -i 's/\r$//' /app/run.sh /app/server.py && chmod +x /app/run.sh /app/server.py /app/bin/pubsub_mock

# Expose default port (HTTP mock + proxy) và gRPC GCP Pub/Sub
EXPOSE 8081 8085

ENV PORT=8081

VOLUME ["/app/certs", "/app/fixtures", "/app/rules", "/app/scenarios", "/app/datasets"]

# Chạy foreground trong container
ENTRYPOINT ["/app/run.sh", "start"]

