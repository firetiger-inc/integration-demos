/**
 * Cloudflare Worker proxy for DataDog telemetry
 * Forwards logs to DataDog (original format) and Firetiger (OTEL format)
 * 
 * Features:
 * - Follows official DataDog proxy specification with ddforward parameter
 * - Converts DataDog logs to OpenTelemetry format for Firetiger
 * - Parallel forwarding for performance
 * - Comprehensive error handling and logging
 */

// Configuration constants - DataDog intake origins by site
const DD_INTAKE_ORIGINS = {
  'datadoghq.com': 'https://browser-intake-datadoghq.com',
  'us3.datadoghq.com': 'https://browser-intake-us3-datadoghq.com', 
  'us5.datadoghq.com': 'https://browser-intake-us5-datadoghq.com',
  'datadoghq.eu': 'https://browser-intake-datadoghq.eu',
  'ap1.datadoghq.com': 'https://browser-intake-ap1-datadoghq.com',
  'ap2.datadoghq.com': 'https://browser-intake-ap2-datadoghq.com',
  'ddog-gov.com': 'https://browser-intake-ddog-gov.com'
};

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight requests
    if (request.method === 'OPTIONS') {
      return handleCORS();
    }

    const url = new URL(request.url);
    
    // Health check endpoint
    if (url.pathname === '/health') {
      const healthData = { 
        status: 'healthy', 
        timestamp: new Date().toISOString(),
        environment: env.ENVIRONMENT || 'development',
        worker: 'ddproxy.rustaml.workers.dev',
        config: {
          dd_forward_enabled: env.DD_FORWARD_ENABLED !== 'false',
          firetiger_configured: !!(env.FIRETIGER_ENDPOINT && env.FIRETIGER_API_KEY)
        }
      };
      console.log('Health check requested:', healthData);
      return new Response(JSON.stringify(healthData, null, 2), {
        headers: { 'Content-Type': 'application/json', ...getCORSHeaders() }
      });
    }

    // DataDog Browser SDK Proxy - look for ddforward parameter
    const ddforward = url.searchParams.get('ddforward');
    if (ddforward && request.method === 'POST') {
      return handleDataDogProxy(request, env, ctx, ddforward);
    }
    
    // Legacy support for direct paths (fallback)
    if (url.pathname.startsWith('/api/v2/') || url.pathname.startsWith('/v1/input/')) {
      return handleDataDogProxy(request, env, ctx, url.pathname + url.search);
    }

    // Default response for unmatched routes
    return new Response('DataDog Proxy Worker - Send requests with ddforward parameter', { 
      status: 404,
      headers: getCORSHeaders()
    });
  }
};

/**
 * Handle DataDog proxy requests following official specification
 * https://docs.datadoghq.com/real_user_monitoring/guide/proxy-rum-data/
 */
async function handleDataDogProxy(request, env, ctx, ddforward) {
  const startTime = Date.now();
  const requestId = generateRequestId();
  
  try {
    // Parse ddforward parameter (URL-encoded path + parameters)
    const decodedForward = decodeURIComponent(ddforward);
    console.log(`[${requestId}] DataDog proxy request - ddforward: ${decodedForward}`);
    
    // Debug logging - log request details
    console.log(`[${requestId}] Headers:`, Object.fromEntries(request.headers.entries()));
    
    // Get request body
    const body = await request.text();
    const bodyPreview = body.length > 500 ? body.substring(0, 500) + '...' : body;
    console.log(`[${requestId}] Payload (${body.length} chars):`, bodyPreview);
    
    // Check kill switch
    if (env.DD_FORWARD_ENABLED === 'false') {
      console.log(`[${requestId}] DataDog forwarding disabled by kill switch`);
      return new Response('OK', { 
        status: 200,
        headers: getCORSHeaders()
      });
    }

    // Determine DataDog site from request headers or default to us5
    const site = extractDataDogSite(request) || 'us5.datadoghq.com';
    const intakeOrigin = DD_INTAKE_ORIGINS[site];
    
    if (!intakeOrigin) {
      throw new Error(`Unsupported DataDog site: ${site}`);
    }
    
    // Build DataDog URL: <INTAKE_ORIGIN>/<PATH><PARAMETERS>
    const datadogUrl = `${intakeOrigin}${decodedForward}`;
    console.log(`[${requestId}] Forwarding to DataDog: ${datadogUrl}`);
    
    // Prepare concurrent requests
    const promises = [];
    
    // 1. Forward to DataDog (always) - following proxy spec exactly
    promises.push(
      fetch(datadogUrl, {
        method: 'POST', // Always POST per spec
        headers: {
          'Content-Type': request.headers.get('Content-Type') || 'application/json',
          'User-Agent': 'DataDog-Proxy-Worker/1.0',
          // Add X-Forwarded-For header for accurate geoIP
          'X-Forwarded-For': getClientIP(request),
          // Forward essential headers, but remove sensitive ones like cookies per spec
          ...(request.headers.get('Origin') && { 'Origin': request.headers.get('Origin') }),
          ...(request.headers.get('Referer') && { 'Referer': request.headers.get('Referer') })
        },
        // Forward raw body unchanged per spec
        body: body
      }).then(async response => {
        const responseText = await response.text();
        console.log(`[${requestId}] DataDog response (${response.status}): ${responseText}`);
        return { 
          service: 'datadog', 
          status: response.status, 
          success: response.ok,
          responseBody: responseText
        };
      }).catch(error => {
        console.log(`[${requestId}] DataDog request failed:`, error.message);
        return {
          service: 'datadog',
          status: 0,
          success: false,
          error: error.message
        };
      })
    );

    // 2. Forward to Firetiger (if configured)
    if (env.FIRETIGER_ENDPOINT && env.FIRETIGER_API_KEY) {
      const firetiger = forwardToFiretiger(body, env.FIRETIGER_ENDPOINT, env.FIRETIGER_API_KEY, requestId);
      promises.push(firetiger);
    } else {
      console.log(`[${requestId}] Firetiger endpoint not configured`);
    }

    // Wait for all requests to complete
    const results = await Promise.allSettled(promises);
    
    // Log results
    const duration = Date.now() - startTime;
    console.log(`[${requestId}] Completed in ${duration}ms:`, results.map(r => 
      r.status === 'fulfilled' ? r.value : { error: r.reason?.message }
    ));

    // Return DataDog's response to maintain compatibility
    const ddResult = results[0];
    if (ddResult.status === 'fulfilled' && ddResult.value.success) {
      return new Response(ddResult.value.responseBody || '', {
        status: ddResult.value.status,
        headers: getCORSHeaders()
      });
    } else {
      throw new Error(`DataDog request failed: ${ddResult.value?.status || ddResult.reason}`);
    }

  } catch (error) {
    console.error(`[${requestId}] Error processing DataDog proxy request:`, error);
    return new Response(error.message, {
      status: 500,
      headers: getCORSHeaders()
    });
  }
}

/**
 * Extract DataDog site from request (for determining correct intake origin)
 */
function extractDataDogSite(request) {
  // Try to extract from various sources
  const url = new URL(request.url);
  
  // From query parameters
  const siteParam = url.searchParams.get('site');
  if (siteParam) return siteParam;
  
  // From headers (if SDK passes it)
  const siteHeader = request.headers.get('X-Datadog-Site');
  if (siteHeader) return siteHeader;
  
  // Default to us5 based on your configuration
  return 'us5.datadoghq.com';
}

/**
 * Get client IP address for X-Forwarded-For header
 */
function getClientIP(request) {
  // Cloudflare provides the real IP in CF-Connecting-IP
  return request.headers.get('CF-Connecting-IP') || 
         request.headers.get('X-Forwarded-For') || 
         request.headers.get('X-Real-IP') || 
         '127.0.0.1';
}

/**
 * Handle DataDog metrics requests (legacy - kept for compatibility)
 */
async function handleMetricsRequest(request, env, ctx) {
  const startTime = Date.now();
  const requestId = generateRequestId();
  
  try {
    console.log(`[${requestId}] Processing metrics request`);
    
    // For now, just forward to DataDog (metrics are lower priority per transcript)
    const url = new URL(request.url);
    const body = await request.text();
    
    const ddUrl = `${DD_METRICS_BASE_URL}${url.pathname}${url.search}`;
    const response = await fetch(ddUrl, {
      method: request.method,
      headers: {
        'Content-Type': request.headers.get('Content-Type') || 'application/json',
        'DD-API-KEY': request.headers.get('DD-API-KEY'),
        'Authorization': request.headers.get('Authorization'),
        'User-Agent': 'DD-Proxy-Worker/1.0'
      },
      body: body
    });

    const duration = Date.now() - startTime;
    console.log(`[${requestId}] Metrics forwarded to DataDog in ${duration}ms: ${response.status}`);

    return new Response(await response.text(), {
      status: response.status,
      headers: { ...Object.fromEntries(response.headers), ...getCORSHeaders() }
    });

  } catch (error) {
    console.error(`[${requestId}] Error processing metrics request:`, error);
    return new Response(JSON.stringify({ 
      success: false, 
      error: error.message,
      requestId 
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...getCORSHeaders() }
    });
  }
}

/**
 * Convert DataDog logs to OpenTelemetry format
 */
function convertDataDogToOTEL(datadogPayload, requestId) {
  let ddLogs;
  
  try {
    const parsed = JSON.parse(datadogPayload);
    // DataDog Browser SDK sends logs in a "logs" array
    ddLogs = parsed.logs || [parsed];
  } catch {
    // If parsing fails, treat as single raw log
    ddLogs = [{
      message: datadogPayload,
      timestamp: Date.now(),
      level: 'info'
    }];
  }

  // Convert each DataDog log to OTEL log format
  const otelLogs = ddLogs.map(ddLog => {
    // Map DataDog severity to OTEL severity
    const severityMap = {
      'debug': { number: 5, text: 'DEBUG' },
      'info': { number: 9, text: 'INFO' },
      'warn': { number: 13, text: 'WARN' },
      'error': { number: 17, text: 'ERROR' }
    };
    
    const severity = severityMap[ddLog.level] || severityMap['info'];
    
    // Convert timestamp (DataDog uses various formats)
    let timeUnixNano;
    if (ddLog.timestamp) {
      const timestamp = new Date(ddLog.timestamp).getTime();
      timeUnixNano = (timestamp * 1000000).toString(); // Convert to nanoseconds
    } else {
      timeUnixNano = (Date.now() * 1000000).toString();
    }

    // Build OTEL log record
    const otelLog = {
      timeUnixNano: timeUnixNano,
      severityNumber: severity.number,
      severityText: severity.text,
      body: {
        stringValue: ddLog.message || JSON.stringify(ddLog)
      },
      attributes: []
    };

    // Convert DataDog attributes to OTEL attributes
    const attributes = [];
    
    // Add DataDog service info as attributes
    if (ddLog.service) {
      attributes.push({
        key: 'service.name',
        value: { stringValue: ddLog.service }
      });
    }
    
    if (ddLog.env) {
      attributes.push({
        key: 'deployment.environment',
        value: { stringValue: ddLog.env }
      });
    }
    
    if (ddLog.version) {
      attributes.push({
        key: 'service.version',
        value: { stringValue: ddLog.version }
      });
    }

    // Add DataDog context as attributes
    Object.keys(ddLog).forEach(key => {
      if (!['message', 'timestamp', 'level', 'service', 'env', 'version'].includes(key)) {
        const value = ddLog[key];
        if (typeof value === 'string') {
          attributes.push({
            key: `dd.${key}`,
            value: { stringValue: value }
          });
        } else if (typeof value === 'number') {
          attributes.push({
            key: `dd.${key}`,
            value: { doubleValue: value }
          });
        } else if (typeof value === 'boolean') {
          attributes.push({
            key: `dd.${key}`,
            value: { boolValue: value }
          });
        } else {
          attributes.push({
            key: `dd.${key}`,
            value: { stringValue: JSON.stringify(value) }
          });
        }
      }
    });

    // Add proxy metadata
    attributes.push(
      {
        key: 'proxy.source',
        value: { stringValue: 'dd-proxy-worker' }
      },
      {
        key: 'proxy.request_id',
        value: { stringValue: requestId }
      },
      {
        key: 'proxy.timestamp',
        value: { stringValue: new Date().toISOString() }
      }
    );

    otelLog.attributes = attributes;
    return otelLog;
  });

  // Build complete OTEL payload
  return {
    resourceLogs: [
      {
        resource: {
          attributes: [
            {
              key: 'service.name',
              value: { stringValue: 'browser-extension' }
            },
            {
              key: 'telemetry.sdk.name',
              value: { stringValue: 'datadog-browser-sdk' }
            },
            {
              key: 'telemetry.sdk.version',
              value: { stringValue: '5.x' }
            }
          ]
        },
        scopeLogs: [
          {
            scope: {
              name: 'dd-proxy-worker',
              version: '1.0.0'
            },
            logRecords: otelLogs
          }
        ]
      }
    ]
  };
}

/**
 * Forward logs to Firetiger via OTEL HTTP
 */
async function forwardToFiretiger(logData, endpoint, apiKey, requestId) {
  try {
    console.log(`[${requestId}] Converting DataDog logs to OTEL format...`);
    
    // Convert DataDog format to OpenTelemetry format
    const otelPayload = convertDataDogToOTEL(logData, requestId);
    
    console.log(`[${requestId}] Forwarding to Firetiger OTEL endpoint: ${endpoint}`);
    console.log(`[${requestId}] OTEL payload preview:`, JSON.stringify(otelPayload, null, 2).substring(0, 500) + '...');

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'User-Agent': 'DD-Proxy-Worker-OTEL/1.0'
      },
      body: JSON.stringify(otelPayload)
    });

    const responseText = await response.text();
    console.log(`[${requestId}] Firetiger OTEL response (${response.status}): ${responseText}`);

    return { 
      service: 'firetiger', 
      status: response.status, 
      success: response.ok,
      format: 'otel-http'
    };

  } catch (error) {
    console.error(`[${requestId}] Error forwarding to Firetiger via OTEL:`, error);
    return { 
      service: 'firetiger', 
      error: error.message, 
      success: false,
      format: 'otel-http'
    };
  }
}

/**
 * Handle CORS preflight requests
 */
function handleCORS() {
  return new Response(null, {
    status: 204,
    headers: getCORSHeaders()
  });
}

/**
 * Get CORS headers
 */
function getCORSHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
    'Access-Control-Max-Age': '86400'
  };
}

/**
 * Generate a unique request ID for tracing
 */
function generateRequestId() {
  return Math.random().toString(36).substring(2, 15);
}