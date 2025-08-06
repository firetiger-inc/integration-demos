#!/bin/bash

# Test DataDog Proxy Worker following official spec
# This simulates what the DataDog Browser SDK sends

PROXY_URL="https://ddproxy.rustaml.workers.dev"
DD_FORWARD_PATH="/api/v2/logs?ddsource=browser&ddtags=sdk_version%3A5.35.1%2Capi%3Afetch%2Cenv%3Aprod%2Cservice%3Atest-app%2Cversion%3A1.0.0&dd-api-key=pub2db6889688c65c5ec7405930704a313a&dd-evp-origin-version=5.35.1&dd-evp-origin=browser&dd-request-id=test-$(date +%s)"

# URL encode the ddforward parameter
DD_FORWARD_ENCODED=$(printf '%s' "$DD_FORWARD_PATH" | jq -sRr @uri)

echo "🧪 Testing DataDog Proxy Worker"
echo "📡 Proxy URL: $PROXY_URL"
echo "🔗 ddforward: $DD_FORWARD_PATH"
echo "🔗 encoded: $DD_FORWARD_ENCODED"
echo ""

# Sample log payload (similar to what Browser SDK sends)
LOG_PAYLOAD='{
  "logs": [{
    "message": "Test log from proxy curl",
    "level": "info",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "service": "test-app",
    "env": "prod",
    "version": "1.0.0",
    "source": "browser",
    "session_id": "test-session-'$(date +%s)'",
    "view": {
      "url": "https://example.com/test"
    }
  }]
}'

echo "📤 Sending test log to proxy..."
echo ""

curl -X POST "$PROXY_URL?ddforward=$DD_FORWARD_ENCODED" \
  -H "Content-Type: application/json" \
  -H "Origin: https://example.com" \
  -H "Referer: https://example.com/test" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -d "$LOG_PAYLOAD" \
  -w "\n\n📊 Response Stats:\n  HTTP Status: %{http_code}\n  Total Time: %{time_total}s\n  Size: %{size_download} bytes\n" \
  -v

echo ""
echo "✅ Test completed!"
echo ""
echo "💡 To monitor worker logs in real-time:"
echo "   npx wrangler tail ddproxy --format pretty"