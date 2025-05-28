# DDTrace to Firetiger via OpenTelemetry Collector

This demo shows how to send traces from a DDTrace-instrumented application to Firetiger via an OpenTelemetry collector, without requiring any code changes to the application.

## How It Works

1. **DDTrace Application** - Python app instrumented with `ddtrace` library
2. **OpenTelemetry Collector** - Runs DataDog receiver on port 8126
3. **Firetiger** - Receives converted traces via OTLP

```
DDTrace App → localhost:8126 → OTel Collector (DataDog Receiver) → Firetiger (OTLP)
```

## Files

### Source (checked in)
- `src/ddtrace_app.py` - Pure DDTrace application (zero OpenTelemetry dependencies)
- `src/setup-firetiger-otel.sh` - Gets Firetiger credentials and generates configs
- `src/requirements.txt` - Python dependencies (just ddtrace + basics)
- `src/docker-compose.yml` - Complete containerized setup
- `src/Dockerfile` - Container for the DDTrace app

### Generated (gitignored)
- `generated/otel-config.yaml` - OpenTelemetry collector configuration
- `generated/.env` - Environment variables
- `generated/start-demo.sh` - Local startup script

## Quick Start

### Setup
```bash
cd src
# Option 1: Get Firetiger credentials automatically from cloud provider
./setup-firetiger-otel.sh --platform gcp --bucket your-bucket --project your-project
# or for AWS:
./setup-firetiger-otel.sh --platform aws --bucket your-bucket --account 123456789012 --region us-west-2

# Option 2: Pass the ingest secret directly (bypasses Secret Manager lookup)
./setup-firetiger-otel.sh --bucket your-bucket --ingest-secret YOUR_SECRET_VALUE
```

### Run with Docker
```bash
cd src
docker-compose up
```

### Run Locally
```bash
cd src
pip install -r requirements.txt
cd ../generated
./start-demo.sh
```

## Key Points

- **No Code Changes**: DDTrace app runs unchanged with `ddtrace-run python app.py`
- **Port 8126**: DDTrace sends to localhost:8126 (standard DataDog agent port)
- **DataDog Receiver**: OTel collector receives and converts DD traces to OpenTelemetry format
- **Zero OTLP Dependencies**: Application has no OpenTelemetry imports or configuration

This approach enables migrating from DataDog to other observability backends without changing application code.