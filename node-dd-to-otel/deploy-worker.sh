#!/bin/bash
# Deploy script for Cloudflare Worker

set -e

echo "📦 Deploying Cloudflare Worker..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create it first."
    echo "💡 Copy .env.example to .env and configure your values"
    exit 1
fi

echo "🔧 Setting secrets from .env file..."

# Load .env file and set secrets
source .env

# Set worker secrets from environment variables
echo "$ENVIRONMENT" | wrangler secret put ENVIRONMENT --env=""
echo "$DD_FORWARD_ENABLED" | wrangler secret put DD_FORWARD_ENABLED --env=""
echo "$OTEL_COLLECTOR_ENDPOINT" | wrangler secret put OTEL_COLLECTOR_ENDPOINT --env=""
echo "$OTEL_COLLECTOR_AUTH" | wrangler secret put OTEL_COLLECTOR_AUTH --env=""

echo "🚀 Deploying worker..."
npm run worker:deploy

echo "✅ Worker deployed successfully!"
echo "🌐 Worker URL: https://ddproxy.rustaml.workers.dev"
echo "🔍 Health check: https://ddproxy.rustaml.workers.dev/health"