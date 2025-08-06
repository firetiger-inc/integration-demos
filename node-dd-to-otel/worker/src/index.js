/**
 * Cloudflare Worker proxy for DataDog telemetry
 * Forwards logs/metrics to both DataDog and Firetiger
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
 * Forward logs to Firetiger
 */
async function forwardToFiretiger(logData, endpoint, apiKey, requestId) {
  try {
    console.log(`[${requestId}] Forwarding to Firetiger: ${endpoint}`);
    
    // Parse the log data to add metadata
    let parsedData;
    try {
      parsedData = JSON.parse(logData);
    } catch {
      parsedData = { raw_log: logData };
    }

    // Enrich with proxy metadata
    const enrichedData = {
      ...parsedData,
      _proxy: {
        source: 'dd-proxy-worker',
        timestamp: new Date().toISOString(),
        requestId: requestId
      }
    };

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'User-Agent': 'DD-Proxy-Worker/1.0'
      },
      body: JSON.stringify(enrichedData)
    });

    return { 
      service: 'firetiger', 
      status: response.status, 
      success: response.ok 
    };

  } catch (error) {
    console.error(`[${requestId}] Error forwarding to Firetiger:`, error);
    return { 
      service: 'firetiger', 
      error: error.message, 
      success: false 
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