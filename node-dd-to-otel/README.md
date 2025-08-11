# DataDog to OTEL Proxy Integration

This project demonstrates a complete telemetry proxy solution that intercepts DataDog logs and metrics and forwards them to both DataDog and Firetiger (OTEL) for enhanced debugging and analysis.

## Architecture Overview

```
Extension/Client App  →  Cloudflare Worker Proxy  →  DataDog + Firetiger
     (logs/metrics)      (intercept & forward)        (dual destination)
```

### Components

1. **Node.js Demo App** (`src/app.js`) - Simulates browser extension sending telemetry
2. **Cloudflare Worker Proxy** (`worker/`) - Intercepts and forwards telemetry
3. **Integration Tests** (`test-integration.js`) - End-to-end testing

## Quick Start

### 1. Install Dependencies
```bash
# Install all dependencies (main project + worker)
npm run install:all
```

### 2. Configure Environment
```bash
# Copy and configure environment variables
cp .env.example .env

# Edit .env with your DataDog credentials:
# DD_CLIENT_TOKEN=your_datadog_client_token
# DD_APPLICATION_ID=your_datadog_application_id  
# DD_API_KEY=your_datadog_api_key (optional, for metrics)
```

### 3. Test the Node.js Demo (Direct to DataDog)
```bash
# Run the demo app - sends telemetry directly to DataDog
npm start
```

### 4. Run Browser Demo (Recommended)
```bash
# Start the demo server with environment variable injection
npm run demo

# Open browser to http://localhost:3000/demo
# Interactive demo with DataDog Browser SDK
```

### 5. Deploy the Cloudflare Worker
```bash
# Start local development
npm run worker:dev

# Or deploy to Cloudflare
cd worker
./setup-secrets.sh staging  # Configure secrets
npm run deploy:staging
```

### 6. Test with Proxy
```bash
# Update .env to use worker as proxy:
# PROXY_ENDPOINT=https://your-worker.workers.dev/logs

# Test integration
npm test
```

## Configuration

### DataDog Setup

1. **Get DataDog RUM Application credentials:**
   - Go to DataDog → RUM → Applications  
   - Create or select your application
   - Copy `Client Token` and `Application ID`

2. **Get DataDog API Key (for metrics):**
   - Go to DataDog → Organization Settings → API Keys
   - Create new key or copy existing

### Worker Environment Variables

Configure via `wrangler secret put`:

```bash
# Kill switch - enables/disables DataDog forwarding
wrangler secret put DD_FORWARD_ENABLED --env staging
# Value: "true" or "false"

# Firetiger endpoint for log forwarding  
wrangler secret put FIRETIGER_ENDPOINT --env staging
# Value: "https://your-firetiger-endpoint.com/api/logs"

# Firetiger API authentication
wrangler secret put FIRETIGER_API_KEY --env staging  
# Value: "your-firetiger-api-key"
```

## Usage

### Direct DataDog Integration (Node.js App)

The demo app simulates a browser extension that sends logs and metrics to DataDog:

```javascript
import ExtensionTelemetry from './src/app.js';

const telemetry = new ExtensionTelemetry();

// Send log
await telemetry.sendLog('info', 'User clicked button', {
  buttonId: 'submit',
  tabId: 123
});

// Send metric  
telemetry.sendMetric('button_clicks', 1, { 
  button: 'submit' 
});
```

### Proxy Mode (via Cloudflare Worker)

Update your application to use the worker endpoint:

```javascript
// Instead of DataDog directly:
const logsEndpoint = 'https://browser-http-intake.logs.datadoghq.com/v1/input/TOKEN';

// Use worker proxy:  
const logsEndpoint = 'https://your-worker.workers.dev/v1/input/TOKEN';
```

The worker will:
- ✅ Forward logs to DataDog (maintains existing functionality)
- ✅ Convert and forward logs to Firetiger in OpenTelemetry format (enables enhanced debugging)  
- ✅ Process both destinations in parallel for performance
- ✅ Respect kill switches for operational control
- ✅ Handle CORS for browser compatibility
- ✅ Provide request tracing and error handling

## OpenTelemetry Integration

The worker automatically converts DataDog log format to OpenTelemetry format when forwarding to Firetiger:

### DataDog → OTEL Conversion
- **Timestamps**: Converted from DataDog format to OTEL `timeUnixNano`
- **Severity Levels**: Mapped to OTEL severity numbers and text
- **Attributes**: All DataDog context preserved as OTEL attributes with `dd.` prefix
- **Resource Info**: Service name, version, and environment mapped to OTEL resource attributes
- **Proxy Metadata**: Added as attributes for traceability

### Test OTEL Conversion
```bash
# Test the conversion logic locally
npm run test:otel
```

## Testing

### Integration Tests
```bash
# Test all endpoints and functionality
npm test

# Test specific worker environment
WORKER_URL=https://your-worker.workers.dev npm test
```

### Manual Testing  
```bash
# Health check
curl https://your-worker.workers.dev/health

# Test log forwarding
curl -X POST https://your-worker.workers.dev/v1/input/YOUR_TOKEN \\
  -H "Content-Type: application/json" \\
  -d '{"message":"test log","level":"info"}'
```

## Deployment

### Worker Deployment

```bash
cd worker

# Deploy to staging
npm run deploy:staging

# Deploy to production  
npm run deploy:production

# Monitor logs
npm run tail:production
```

### Gradual Rollout Strategy

1. **Deploy with Kill Switch OFF**
   ```bash
   wrangler secret put DD_FORWARD_ENABLED --env production <<< "false"
   ```

2. **Update Client to Use Proxy** (with kill switch disabled, requests bypass worker)

3. **Enable Proxy Gradually**  
   ```bash
   wrangler secret put DD_FORWARD_ENABLED --env production <<< "true"
   ```

4. **Monitor and Rollback if Needed**
   ```bash  
   wrangler secret put DD_FORWARD_ENABLED --env production <<< "false"
   ```

## Monitoring & Troubleshooting

### Worker Logs
```bash
# Real-time logs
wrangler tail --env production

# Search recent logs  
wrangler tail --env production --search "ERROR"
```

### Health Monitoring
```bash
# Automated health check
curl -f https://your-worker.workers.dev/health || echo "Worker unhealthy"
```

### Common Issues

**1. CORS Errors**
- Worker automatically handles CORS headers
- Check browser dev tools for specific CORS issues

**2. DataDog Authentication Errors**  
- Verify `DD_CLIENT_TOKEN` is correct
- Check DataDog RUM application configuration

**3. Firetiger Forwarding Failures**
- Firetiger failures don't affect DataDog forwarding  
- Check worker logs for specific error details
- Verify `FIRETIGER_ENDPOINT` and `FIRETIGER_API_KEY`

**4. High Latency**
- Worker runs requests to DataDog and Firetiger in parallel
- Monitor worker execution time in logs

## Benefits

### For Browser Extensions (Immediate)
- ✅ **No Client Changes Required** - Just update endpoint URL
- ✅ **Operational Control** - Kill switches and gradual rollout
- ✅ **Maintained DataDog Integration** - Existing workflows continue
- ✅ **Ad Block Resistance** - All traffic from custom domain  

### For Firetiger (Long-term)
- ✅ **Real Client Data** - Access to production telemetry streams
- ✅ **Enhanced Context** - Cross-reference with existing DataDog data
- ✅ **Debugging Insights** - Apply ML analysis to real extension bugs

### For Both
- ✅ **Cost Efficiency** - Shared integration development costs
- ✅ **Scalable Pattern** - Reusable for other customer integrations

## Security Considerations  

- 🔒 Worker handles sensitive DataDog tokens securely
- 🔒 Firetiger API keys stored as Cloudflare secrets
- 🔒 No logging of sensitive telemetry data in worker
- 🔒 CORS properly configured for browser security

## Cost Analysis

### Cloudflare Worker Costs
- **Requests**: 100k free, then $0.50 per million  
- **CPU Time**: 10ms free per request, then $12.50 per million GB-s
- **Estimated Monthly Cost**: ~$10-50 for moderate telemetry volume

### DataDog Integration
- **No Additional Costs** - Same logs/metrics still sent to DataDog  
- **Potential Savings** - Better debugging = fewer DataDog query costs

## Next Steps

1. **Production Deployment**: Deploy worker and configure secrets
2. **Client Integration**: Update browser extension to use worker endpoint  
3. **Monitoring Setup**: Configure alerts and health checks
4. **Firetiger Analysis**: Begin ML analysis on telemetry data  
5. **Iteration**: Enhance based on real-world usage patterns

---

## Support

For questions or issues:
- **Firetiger Team**: rustam@firetiger.com
  
- **GitHub Issues**: [Create issue](https://github.com/your-repo/issues)