#!/bin/bash

# Test script for validating DataDog metrics integration scenarios

set -e

echo "=== DataDog Metrics Integration Test Scenarios ==="
echo ""

print_usage() {
    echo "Usage: $0 [traces-to-otel-metrics-to-dd|traces-and-metrics-to-otel]"
    echo ""
    echo "Scenarios:"
    echo "  traces-to-otel-metrics-to-dd  - VALIDATES: OTEL handles traces only, DataDog agent receives metrics"
    echo "  traces-and-metrics-to-otel   - VALIDATES: OTEL interference by intercepting both traces and metrics"
    echo ""
    echo "ACCEPTANCE CRITERIA:"
    echo "  traces-to-otel-metrics-to-dd: Metrics reach simulated DataDog agent (no interference)"
    echo "  traces-and-metrics-to-otel: Both traces and metrics intercepted by OTEL collector (shows interference)"
}

cleanup() {
    echo "Cleaning up containers..."
    # Stop containers from all profiles
    docker-compose --profile traces-to-otel-metrics-to-dd down --remove-orphans 2>/dev/null || true
    docker-compose --profile traces-and-metrics-to-otel down --remove-orphans 2>/dev/null || true
    # Also try without profiles to catch any default containers
    docker-compose down --remove-orphans 2>/dev/null || true
}

test_traces_to_otel_metrics_to_dd() {
    echo "🔍 Testing Scenario: TRACES TO OTEL, METRICS TO DATADOG"
    echo "   - OTEL collector receives traces on port 8126 (and forwards to Firetiger)"
    echo "   - Simulated DataDog agent receives metrics on port 8125"
    echo "   - This validates the production scenario: NO INTERFERENCE"
    echo ""
    
    cleanup
    
    export SCENARIO=traces-only
    export DOGSTATSD_HOST=datadog-agent
    export DOGSTATSD_PORT=8125
    
    echo "Starting containers with SCENARIO=$SCENARIO and DataDog agent simulator..."
    docker-compose --profile traces-to-otel-metrics-to-dd up -d
    
    echo "✅ Scenario running. Check logs with:"
    echo "   docker-compose logs -f otel-collector     # Should show traces only"
    echo "   docker-compose logs -f datadog-agent      # Should show 'METRIC RECEIVED:' messages"
    echo "   docker-compose logs -f ddtrace-app        # Should show metrics routing to datadog-agent"
    echo ""
    echo "🎯 ACCEPTANCE CRITERIA:"
    echo "   ✅ OTEL collector receives and forwards traces to Firetiger"
    echo "   ✅ DataDog agent simulator receives StatsD metrics"
    echo "   ✅ No metrics appear in OTEL collector logs"
    echo "   ✅ Application logs show metrics routing to 'datadog-agent'"
}

test_traces_and_metrics_to_otel() {
    echo "🔍 Testing Scenario: TRACES AND METRICS TO OTEL"
    echo "   - OTEL collector receives traces on port 8126"
    echo "   - OTEL collector also intercepts metrics on port 8125"
    echo "   - This tests OTEL collector interference with DataDog metrics flow"
    echo ""
    
    cleanup
    
    export SCENARIO=traces-and-metrics
    export DOGSTATSD_HOST=otel-collector
    export DOGSTATSD_PORT=8125
    
    echo "Starting containers with SCENARIO=$SCENARIO..."
    docker-compose --profile traces-and-metrics-to-otel up -d
    
    echo "✅ Scenario running. Check logs with:"
    echo "   docker-compose logs -f otel-collector     # Should show traces AND metrics"
    echo "   docker-compose logs -f ddtrace-app        # Should show metrics routing to otel-collector"
    echo ""
    echo "🚨 INTERFERENCE VALIDATION:"
    echo "   ❌ OTEL collector intercepts both traces AND metrics"
    echo "   ❌ Metrics go to OTEL/Firetiger instead of DataDog"
    echo "   ❌ Application logs show metrics routing to 'otel-collector'"
    echo "   ❌ This breaks existing DataDog metrics flow"
}

case "${1:-}" in
    traces-to-otel-metrics-to-dd)
        test_traces_to_otel_metrics_to_dd
        ;;
    traces-and-metrics-to-otel)
        test_traces_and_metrics_to_otel
        ;;
    clean|cleanup)
        cleanup
        echo "✅ Cleanup completed"
        ;;
    "")
        print_usage
        echo ""
        echo "🚀 Quick test commands:"
        echo "  $0 traces-to-otel-metrics-to-dd  # ✅ VALIDATE: Metrics reach DataDog agent (no interference)"
        echo "  $0 traces-and-metrics-to-otel   # ❌ VALIDATE: OTEL intercepts both traces and metrics"
        echo "  $0 cleanup                       # Stop all containers"
        echo ""
        echo "🎯 ACCEPTANCE CRITERIA:"
        echo "  Success: 'METRIC RECEIVED:' messages in DataDog agent logs (traces-to-otel-metrics-to-dd)"
        echo "  Failure: Metrics appear in OTEL collector logs (traces-and-metrics-to-otel)"
        ;;
    *)
        echo "❌ Unknown scenario: $1"
        print_usage
        exit 1
        ;;
esac