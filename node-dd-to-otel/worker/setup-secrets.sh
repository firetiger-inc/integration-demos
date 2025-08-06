#!/bin/bash
# Setup script for Cloudflare Worker secrets
# Usage: ./setup-secrets.sh [staging|production]

ENV=${1:-staging}

echo "Setting up secrets for environment: $ENV"

# Function to set secret
set_secret() {
  local key=$1
  local prompt=$2
  
  echo -n "$prompt: "
  read -s value
  echo
  
  if [ ! -z "$value" ]; then
    echo "Setting $key..."
    wrangler secret put "$key" --env "$ENV" <<< "$value"
  else
    echo "Skipping $key (no value provided)"
  fi
}

echo
echo "Configure DataDog forwarding (kill switch):"
echo "Enter 'true' to enable forwarding, 'false' to disable"
set_secret "DD_FORWARD_ENABLED" "Enable DataDog forwarding (true/false)"

echo
echo "Configure Firetiger endpoint:"
set_secret "FIRETIGER_ENDPOINT" "Firetiger API endpoint URL"

echo
echo "Configure Firetiger authentication:"
set_secret "FIRETIGER_API_KEY" "Firetiger API key"

echo
echo "✅ Secrets setup complete for environment: $ENV"
echo
echo "To verify deployment:"
echo "  wrangler tail --env $ENV"
echo
echo "To test the health endpoint:"
echo "  curl https://dd-to-otel-proxy.$ENV.your-subdomain.workers.dev/health"