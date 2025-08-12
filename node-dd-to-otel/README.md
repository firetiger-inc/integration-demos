# DataDog to OTEL Integration Demo

This demo consists of two main components that work together to capture and forward telemetry data:

## Components

### 1. Local Demo Server
- **Purpose**: Simulates a browser application that generates telemetry events
- **Technology**: Express.js server with DataDog Browser SDK integration
- **Features**: Interactive web interface to generate different types of log events
- **Runs on**: `http://localhost:3000`

### 2. Cloudflare Worker Proxy
- **Purpose**: Intercepts telemetry data and forwards to multiple destinations
- **Technology**: Cloudflare Worker that follows DataDog proxy specification
- **Features**: 
  - Forwards original data to DataDog (maintains compatibility)
  - Converts data to OTEL format and sends to collector
  - Parallel processing for performance
- **Deployed to**: Cloudflare Workers platform

## Architecture Flow

```
Local Demo Server (Browser SDK) → Cloudflare Worker Proxy → DataDog (original format)
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

The deployment script automatically reads your `.env` file and sets the necessary secrets:

```bash
# Deploy using the automated script (recommended)
./deploy-worker.sh
```

**What the script does:**
1. Loads variables from `.env` file
2. Sets them as Cloudflare Worker secrets using `wrangler secret put`
3. Deploys the worker to production

**Manual deployment** (if you prefer to manage secrets separately):
```bash
# Set secrets manually
echo "value" | wrangler secret put ENVIRONMENT
echo "value" | wrangler secret put DD_FORWARD_ENABLED  
echo "value" | wrangler secret put OTEL_COLLECTOR_ENDPOINT
echo "value" | wrangler secret put OTEL_COLLECTOR_AUTH

# Then deploy
npm run worker:deploy
```

**Worker Environment Variables** (set as Cloudflare secrets):
- `ENVIRONMENT`: Environment name (staging/production)
- `DD_FORWARD_ENABLED`: Controls DataDog forwarding (kill switch)
- `OTEL_COLLECTOR_ENDPOINT`: OTEL collector endpoint URL
- `OTEL_COLLECTOR_AUTH`: Authorization header for OTEL collector

## Usage

### Component 1: Local Demo Server

The Express server provides an interactive web interface to generate telemetry events.

1. **Start the server:**
   ```bash
   npm run demo
   # or
   node server.js
   ```

2. **Open the demo interface:**
   ```
   http://localhost:3000/demo
   ```

3. **Generate telemetry events:**
   - Click buttons to simulate different log events (info, warn, error)
   - View real-time console output
   - Toggle between direct DataDog mode and proxy mode
   - Monitor configuration status

### Component 2: Cloudflare Worker Proxy

The worker intercepts telemetry from the demo server and forwards to multiple destinations.

**Features:**
- Receives DataDog Browser SDK requests via `ddforward` parameter
- Forwards original payload to DataDog (maintains compatibility)
- Converts to OTEL format and sends to collector
- Provides health check endpoint at `/health`

**How it works:**
1. Demo server sends telemetry with `?ddforward=...` parameter
2. Worker extracts and forwards to DataDog endpoint
3. Worker converts to OTEL format and sends to collector
4. Both operations happen in parallel for performance

## Available Scripts

### Demo Server Scripts
```bash
npm run demo          # Start demo server (production config)
npm run demo:dev      # Start demo server with auto-reload (production config)
npm run demo:staging  # Start demo server (staging config for local development)
```

### Worker Scripts
```bash
npm run worker:dev           # Start worker locally (uses .env.staging)
npm run worker:deploy        # Deploy worker to production
```

### Testing Scripts
```bash
npm test              # Run integration tests
npm run test:server   # Test Express server functionality
npm run test:otel     # Test OTEL conversion logic
```

## Local Development & Testing

You can test the entire integration locally using staging environment configuration:

### 1. Set up staging environment
```bash
# Copy the staging environment template
cp .env.staging.example .env.staging
# Edit .env.staging with your actual credentials
```

### 2. Start the Worker Locally (Terminal 1)
```bash
npm run worker:dev
# Worker runs on http://localhost:8787 using .env.staging config
```

### 3. Start the Demo Server (Terminal 2)
```bash
npm run demo:staging
# Demo server runs on http://localhost:3000 using .env.staging config
```

### 4. Test the Integration
1. Open `http://localhost:3000/demo`
2. The demo will automatically use the local worker (proxy mode)
3. Generate telemetry events using the buttons
4. Check both terminals to see logs from both components

### Environment Configuration
- **Production**: Uses `.env` with deployed worker endpoint
- **Staging/Local**: Uses `.env.staging` with `http://localhost:8787`
- **Wrangler**: Automatically loads `.env.staging` when using `--env staging`

### Local Testing Benefits
- ✅ Clean separation between production and development configs
- ✅ No need to deploy worker for testing
- ✅ See real-time logs from both components
- ✅ Test OTEL conversion locally
- ✅ Faster development iteration
- ✅ Test CORS and proxy functionality

## Testing

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

**Note**: The demo interface includes a toggle button to switch between direct DataDog mode and proxy mode - no code changes needed!

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