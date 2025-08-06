import { config } from 'dotenv';

config();

// Minimal browser globals needed for DataDog Browser SDK
if (!global.window) global.window = global;
if (!global.document) {
  global.document = { 
    createElement: () => ({}),
    body: {},
    addEventListener: () => {},
    dispatchEvent: () => {},
    readyState: 'complete',
    hidden: false
  };
}
if (!global.Event) {
  global.Event = class Event {
    constructor(type) { this.type = type; }
  };
}

// Add fetch debugging to see if SDK makes requests
const originalFetch = global.fetch;
global.fetch = async function(url, options) {
  if (url.includes('datadoghq.com')) {
    console.log(`🌐 DATADOG FETCH: ${options?.method || 'GET'} ${url}`);
    console.log(`📤 FETCH BODY: ${options?.body ? options.body.substring(0, 100) + '...' : 'none'}`);
  }
  
  // If no original fetch, we need to provide one
  if (!originalFetch) {
    const fetch = (await import('node-fetch')).default;
    return fetch(url, options);
  }
  
  return originalFetch(url, options);
};
if (!global.navigator) {
  Object.defineProperty(global, 'navigator', { 
    value: { userAgent: 'Chrome/119.0.0.0 (Node.js Simulation)' },
    writable: true
  });
}
if (!global.location) {
  Object.defineProperty(global, 'location', { 
    value: { href: 'http://localhost' },
    writable: true
  });
}

// Import DataDog Browser SDK - it can work in Node.js with minimal globals!
const { datadogLogs } = await import('@datadog/browser-logs');

// Configuration for Browser Extension Simulation
const DD_CLIENT_TOKEN = process.env.DD_CLIENT_TOKEN;
const DD_SITE = process.env.DD_SITE || 'datadoghq.com';
const DD_SERVICE = process.env.DD_SERVICE || 'browser-extension';
const DD_ENV = process.env.DD_ENV || 'demo';
const DD_VERSION = process.env.DD_VERSION || '2.1.0';
const PROXY_ENDPOINT = process.env.PROXY_ENDPOINT; // Cloudflare Worker endpoint

class ExtensionTelemetry {
  constructor() {
    this.sessionId = this.generateSessionId();
    this.startTime = Date.now();
    this.isInitialized = false;
    
    this.initializeDataDog();
  }

  initializeDataDog() {
    if (!DD_CLIENT_TOKEN) {
      console.log('⚠️  DD_CLIENT_TOKEN not configured - DataDog logging disabled');
      return;
    }

    // Configure DataDog Browser Logs SDK
    const config = {
      clientToken: DD_CLIENT_TOKEN,
      site: DD_SITE,
      forwardErrorsToLogs: true,
      sessionSampleRate: 100,
      service: DD_SERVICE,
      env: DD_ENV,
      version: DD_VERSION
    };

    // Use official proxy parameter if proxy endpoint is configured
    if (PROXY_ENDPOINT) {
      config.proxy = PROXY_ENDPOINT;
      console.log(`🔄 DataDog Browser Logs SDK configured to use proxy: ${PROXY_ENDPOINT}`);
    } else {
      console.log('📡 DataDog Browser Logs SDK configured for direct connection');
    }

    // Initialize DataDog Browser Logs
    datadogLogs.init(config);

    // Set global context for the session
    datadogLogs.setGlobalContextProperty('sessionId', this.sessionId);
    datadogLogs.setGlobalContextProperty('userAgent', 'Chrome/119.0.0.0 (Simulated Browser Extension)');
    datadogLogs.setGlobalContextProperty('extensionVersion', DD_VERSION);
    datadogLogs.setGlobalContextProperty('proxyMode', !!PROXY_ENDPOINT);

    this.isInitialized = true;
    console.log(`✓ DataDog Browser Logs SDK initialized for service: ${DD_SERVICE}`);
    console.log(`✓ Site: ${DD_SITE}`);
  }

  generateSessionId() {
    return 'session_' + Math.random().toString(36).substring(2, 15);
  }

  // Send logs using DataDog Browser SDK
  sendLog(level, message, context = {}) {
    if (!this.isInitialized) {
      console.log(`📝 Log (SDK disabled) [${level.toUpperCase()}]: ${message}`);
      return;
    }

    const logContext = {
      ...context,
      timing: Date.now() - this.startTime,
      iteration: context.iteration || 'startup'
    };

    // Use DataDog Browser SDK logging methods
    switch (level) {
      case 'debug':
        datadogLogs.logger.debug(message, logContext);
        break;
      case 'info':
        datadogLogs.logger.info(message, logContext);
        break;
      case 'warn':
        datadogLogs.logger.warn(message, logContext);
        break;
      case 'error':
        datadogLogs.logger.error(message, logContext);
        break;
      default:
        datadogLogs.logger.info(message, logContext);
    }

    console.log(`✓ Log sent via DataDog Browser SDK [${level.toUpperCase()}]: ${message}`);
    
    // Try to force immediate flush by simulating page activity
    setTimeout(() => {
      if (global.document && global.document.dispatchEvent) {
        global.document.dispatchEvent(new Event('visibilitychange'));
      }
    }, 100);
  }

  // Add custom error handling for browser context
  sendError(error, context = {}) {
    if (!this.isInitialized) {
      console.log(`🚨 Error (SDK disabled): ${error.message}`);
      return;
    }

    datadogLogs.logger.error(error.message, {
      ...context,
      error: {
        stack: error.stack,
        name: error.name,
        message: error.message
      },
      sessionId: this.sessionId,
      timing: Date.now() - this.startTime
    });

    console.log(`✓ Error sent via DataDog Browser SDK: ${error.message}`);
  }

  // Simulate extension activity with browser-specific events
  async simulateExtensionActivity() {
    console.log(`🚀 Starting browser extension simulation (Session: ${this.sessionId})`);
    console.log(`📡 Service: ${DD_SERVICE}, Env: ${DD_ENV}, Version: ${DD_VERSION}`);
    console.log(`📡 Using ${PROXY_ENDPOINT ? 'PROXY' : 'DIRECT'} mode`);
    
    if (PROXY_ENDPOINT) {
      console.log(`🔗 Proxy endpoint: ${PROXY_ENDPOINT}`);
    }

    // Initial startup log
    this.sendLog('info', 'Browser extension initialized', {
      userAgent: 'Chrome/119.0.0.0 (Simulated Browser Extension)',
      proxyMode: !!PROXY_ENDPOINT,
      startup: true,
      url: 'https://example.com'
    });

    let iteration = 1;
    const simulate = async () => {
      try {
        // Browser extension specific interactions
        const interactions = [
          { 
            action: 'page_capture', 
            level: 'info', 
            message: 'User captured page screenshot',
            context: { 
              tabId: Math.floor(Math.random() * 10) + 1,
              url: `https://example.com/page-${Math.floor(Math.random() * 100)}`,
              captureType: 'screenshot'
            }
          },
          { 
            action: 'bug_report', 
            level: 'info', 
            message: 'User submitted bug report',
            context: { 
              reportId: `bug_${Date.now()}`,
              category: 'ui-issue',
              severity: 'medium'
            }
          },
          { 
            action: 'network_error', 
            level: 'error', 
            message: 'Network request failed in content script',
            context: { 
              errorCode: 'NETWORK_ERROR',
              endpoint: 'https://api.example.com/data',
              retryCount: 3
            }
          },
          { 
            action: 'performance_slow', 
            level: 'warn', 
            message: 'Slow performance detected in extension',
            context: { 
              loadTime: Math.floor(Math.random() * 5000) + 1000,
              component: 'content-script',
              memoryUsage: Math.floor(Math.random() * 100) + 50
            }
          },
          {
            action: 'user_interaction',
            level: 'debug',
            message: 'User clicked extension icon',
            context: {
              clickPosition: { x: Math.floor(Math.random() * 1920), y: Math.floor(Math.random() * 1080) },
              timestamp: Date.now()
            }
          }
        ];

        const interaction = interactions[Math.floor(Math.random() * interactions.length)];
        
        // Add iteration context
        const contextWithIteration = {
          ...interaction.context,
          iteration: iteration,
          action: interaction.action,
          sessionDuration: Date.now() - this.startTime
        };
        
        // Send log using DataDog Browser SDK
        this.sendLog(interaction.level, interaction.message, contextWithIteration);

        // Occasionally simulate an error
        if (Math.random() < 0.05) { // 5% chance
          try {
            throw new Error(`Simulated extension error during ${interaction.action}`);
          } catch (error) {
            this.sendError(error, { 
              action: interaction.action, 
              iteration: iteration 
            });
          }
        }

        iteration++;
      } catch (error) {
        this.sendError(error, { iteration: iteration });
      }

      // Schedule next interaction with realistic timing
      setTimeout(simulate, Math.random() * 5000 + 3000); // Random delay 3-8s
    };

    // Start simulation
    simulate();
  }

  // Graceful shutdown for browser context
  async shutdown() {
    this.sendLog('info', 'Browser extension shutting down', {
      sessionDuration: Date.now() - this.startTime,
      totalInteractions: Math.floor((Date.now() - this.startTime) / 5000),
      shutdownReason: 'user_requested'
    });
    
    // Give time for final logs to be sent
    setTimeout(() => {
      console.log('🔍 Simulation completed');
      process.exit(0);
    }, 2000);
  }
}

// Main execution
async function main() {
  if (!DD_CLIENT_TOKEN) {
    console.error('❌ DD_CLIENT_TOKEN environment variable is required for Browser SDK');
    console.error('💡 Note: Browser SDK uses CLIENT_TOKEN, not API_KEY');
    process.exit(1);
  }

  console.log('🌐 Initializing DataDog Browser SDK in simulated environment...');
  
  const telemetry = new ExtensionTelemetry();

  // Handle graceful shutdown
  process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down gracefully...');
    telemetry.shutdown();
  });

  // Start simulation
  await telemetry.simulateExtensionActivity();
}

main().catch((error) => {
  console.error('💥 Fatal error:', error.message);
  process.exit(1);
});