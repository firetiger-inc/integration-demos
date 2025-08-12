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

echo "🔧 Using .env file for configuration"
npm run worker:deploy

echo "✅ Worker deployed successfully!"
echo "🌐 Worker URL: https://ddproxy.rustaml.workers.dev"
echo "🔍 Health check: https://ddproxy.rustaml.workers.dev/health"