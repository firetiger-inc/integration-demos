# DDTrace to Firetiger via OpenTelemetry Collector

This demo shows how to send traces from a DDTrace-instrumented application to Firetiger via an OpenTelemetry collector, without requiring any code changes to the application. It also validates whether the OTEL collector interferes with DataDog metrics delivery.

## How It Works

1. **DDTrace Application** - Python app instrumented with `ddtrace` library and DataDog metrics (DogStatsD)
2. **OpenTelemetry Collector** - Runs DataDog receiver on port 8126 (traces), optionally on port 8125 (metrics)
3. **Firetiger** - Receives converted traces via OTLP

```
DDTrace App → localhost:8126 → OTel Collector (DataDog Receiver) → Firetiger (OTLP)
DDTrace App → localhost:8125 → [DataDog Agent OR OTEL Collector] → [DataDog OR Firetiger]
```

## 🔍 Metrics Validation Scenarios

This demo includes three test scenarios to validate whether OTEL collector interferes with DataDog metrics:

### Scenario 1: Traces to OTEL, Metrics to DataDog (Production Recommended)
- **Traces**: DDTrace → OTEL Collector (port 8126) → Firetiger
- **Metrics**: DogStatsD → DataDog Agent (port 8125) → DataDog
- **Result**: No interference - metrics flow directly to DataDog

### Scenario 2: Traces and Metrics to OTEL (Interference Testing)
- **Traces**: DDTrace → OTEL Collector (port 8126) → Firetiger  
- **Metrics**: DogStatsD → OTEL Collector (port 8125) → Firetiger
- **Result**: OTEL collector intercepts metrics - validates the interference concern

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

## Quick Start

### Setup
```bash
cd src
# Get Firetiger credentials and generate configs
./setup-firetiger-otel.sh --platform gcp --bucket your-bucket --project your-project
# or for AWS:
./setup-firetiger-otel.sh --platform aws --bucket your-bucket --account 123456789012 --region us-west-2
```

### Test Metrics Interference Scenarios

The easiest way to test all scenarios is using the test script:

```bash
cd src

# ✅ VALIDATE: Metrics reach DataDog agent (no interference)
./test-scenarios.sh traces-to-otel-metrics-to-dd

# ❌ VALIDATE: OTEL intercepts both traces and metrics (shows interference)
./test-scenarios.sh traces-and-metrics-to-otel

# Clean up
./test-scenarios.sh cleanup
```

**Quick validation:**
```bash
# After running traces-to-otel-metrics-to-dd, check for successful metrics delivery:
docker-compose logs datadog-agent | grep "METRIC RECEIVED:"

# After running traces-and-metrics-to-otel, check for interference:
docker-compose logs otel-collector | grep -i statsd
```

### Manual Docker Testing
```bash
cd src

# Scenario 1: Traces to OTEL, metrics to DataDog - no interference
SCENARIO=traces-only docker-compose --profile traces-to-otel-metrics-to-dd up

# Scenario 2: Traces and metrics to OTEL - test interference  
SCENARIO=traces-and-metrics docker-compose --profile traces-and-metrics-to-otel up
```

## 🔍 Validating Results

### What to Look For

**Application Logs:**
```bash
docker-compose logs ddtrace-app
```
Look for:
- `✅ METRICS ROUTING: DogStatsD configured to send directly to DataDog agent` (good)
- `⚠️ METRICS ROUTING: DogStatsD configured to send to OTEL collector` (interference test)

**OTEL Collector Logs:**
```bash  
docker-compose logs otel-collector
```
Look for:
- Traces being received and exported to Firetiger
- Metrics being received (only in `traces-and-metrics` scenario)
- Configuration loading messages

**Key Metrics to Monitor:**
- `webapp.app.started` - Application startup counter
- `webapp.web.requests.total` - Request count by endpoint
- `webapp.web.requests.duration` - Request latency histogram
- `webapp.app.metrics_test.*` - Validation metrics (heartbeat, connectivity)

### Expected Results by Scenario

| Scenario | Traces Destination | Metrics Destination | ACCEPTANCE CRITERIA |
|----------|-------------------|-------------------|---------------------|
| `traces-to-otel-metrics-to-dd` | ✅ OTEL Collector → Firetiger | ✅ DataDog Agent (UDP listener) | ✅ **"METRIC RECEIVED:" in agent logs** |
| `traces-and-metrics-to-otel` | ✅ OTEL Collector → Firetiger | ❌ OTEL Collector → Firetiger | ❌ **Metrics in OTEL collector logs** |

### 🎯 Acceptance Criteria

**SUCCESS (No Interference):**
```bash
docker-compose logs datadog-agent | grep "METRIC RECEIVED:"
# Should show: [DataDog Agent Sim] METRIC RECEIVED: webapp.app.started:1|c|#env:demo...
```

**FAILURE (Interference Detected):**
```bash
docker-compose logs otel-collector | grep -i metric
# Should show metrics being processed by OTEL collector instead of DataDog agent
```

## Key Points

- **No Code Changes**: DDTrace app runs unchanged with `ddtrace-run python app.py`
- **Port 8126**: DDTrace sends traces to localhost:8126 (standard DataDog agent port)  
- **Port 8125**: DogStatsD sends metrics to localhost:8125 (configurable destination)
- **DataDog Receiver**: OTel collector receives and converts DD traces to OpenTelemetry format
- **Metrics Validation**: Application includes DogStatsD metrics to test delivery paths
- **Zero OTLP Dependencies**: Application has no OpenTelemetry imports or configuration

## Production Recommendations

Based on the test results:

1. **Configure OTEL collector for traces only** (`traces-only` scenario)
2. **Keep DataDog agent running for metrics** on port 8125
3. **Configure DD_DOGSTATSD_HOST to point to DataDog agent**, not OTEL collector
4. **Monitor metrics delivery** to ensure no interference

This approach enables migrating traces to other observability backends while preserving DataDog metrics flow.