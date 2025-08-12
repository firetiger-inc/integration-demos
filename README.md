# Firetiger Demo Collection

This directory contains demonstration applications showing different ways to send telemetry data to Firetiger.

## Demos

### [otel-logs/](./otel-logs/)
Direct OpenTelemetry logs example using the `telemetry.py` script. Sends structured logs directly to Firetiger via OTLP.

### [ddtrace-to-otel/](./ddtrace-to-otel/)
DDTrace to OpenTelemetry collector example. Shows how to instrument applications with DataDog's `ddtrace` library and forward traces to Firetiger via an OpenTelemetry collector using the DataDog receiver.

## Getting Started

Each demo directory contains its own README with specific setup instructions.

## Structure

- `*/src/` - Source code and configuration files (checked into git)
- `*/generated/` - Generated configuration files and credentials (gitignored)
- `*/README.md` - Demo-specific documentation