#\!/bin/bash
# Deploy script that sources .env and deploys the worker

set -e

# Check if .env exists
if [ \! -f .env ]; then
    echo "❌ .env file not found. Please create it first."
    echo "💡 Copy .env.example to .env and configure your values"
    exit 1
fi

echo "📦 Deploying Cloudflare Worker..."

# Source .env and deploy
source .env && cd worker && wrangler deploy

echo "✅ Worker deployed successfully\!"
echo "🌐 Worker URL: https://ddproxy.rustaml.workers.dev"
echo "🔍 Health check: https://ddproxy.rustaml.workers.dev/health"
EOF < /dev/null