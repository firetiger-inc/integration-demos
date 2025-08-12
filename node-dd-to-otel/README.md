# DataDog to OTEL Integration Demo

This demo shows how to proxy DataDog Browser SDK telemetry through a Cloudflare Worker that forwards data to both DataDog and an OpenTelemetry (OTEL) collector.

## Architecture

```
Browser App → Cloudflare Worker Proxy → DataDog (original format)
                    ↓
              OTEL Collector → Firetiger (OTEL format)
```

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# DataDog Configuration (for browser demo)
DD_CLIENT_TOKEN=your_datadog_client_token_here
DD_SITE=us5.datadoghq.com
DD_SERVICE=browser-extension
DD_ENV=staging
DD_VERSION=1.0.0

# Worker Configuration (for browser demo)
PROXY_ENDPOINT=https://your-worker-name.your-subdomain.workers.dev

# Worker Environment Variables (for deployment)
ENVIRONMENT=staging
DD_FORWARD_ENABLED=true
OTEL_COLLECTOR_ENDPOINT=https://your-otel-collector-endpoint.com:443
OTEL_COLLECTOR_AUTH=Basic your_base64_encoded_credentials_here
```

**Important:** The `.env` file now contains all configuration for both the browser demo and worker deployment. Keep this file secure and never commit it to version control.

### 3. Deploy the Cloudflare Worker

With the flattened structure, everything is in the root directory and wrangler reads from the same `.env` file:

```bash
# Easy deployment using the provided script
./deploy-worker.sh

# Or manually:
npm run worker:deploy
```

**Worker Environment Variables (from .env file):**
- `ENVIRONMENT`: Environment name (staging/production)
- `DD_FORWARD_ENABLED`: Controls DataDog forwarding (kill switch)
- `OTEL_COLLECTOR_ENDPOINT`: OTEL collector endpoint URL
- `OTEL_COLLECTOR_AUTH`: Authorization header for OTEL collector

## Usage

### Run the Browser Demo

1. **Start the Express server:**
   ```bash
   npm run demo
   # or
   node server.js
   ```

2. **Open the demo in your browser:**
   ```
   http://localhost:3000/demo
   ```

The demo page will show:
- Current configuration status
- Buttons to simulate different log events
- Console output showing telemetry being sent
- Toggle between direct DataDog mode and proxy mode

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
# Deploy the worker
npm run worker:deploy

# Or use the deployment script
./deploy-worker.sh

# Monitor logs
wrangler tail
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