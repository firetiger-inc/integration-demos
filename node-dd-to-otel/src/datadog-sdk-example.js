import { datadogLogs } from '@datadog/browser-logs';

// Standard DataDog SDK initialization
datadogLogs.init({
  clientToken: 'your_client_token',
  site: 'datadoghq.com',
  service: 'browser-extension',
  env: 'production',
  version: '2.1.0'
});

// Problem: DataDog SDK doesn't officially support custom endpoints
// The SDK hardcodes endpoints like:
// https://browser-http-intake.logs.datadoghq.com

// Workaround options:

// Option 1: Override fetch globally (hacky but works)
const originalFetch = global.fetch;
global.fetch = function(url, options) {
  if (url.includes('browser-http-intake.logs.datadoghq.com')) {
    url = url.replace('browser-http-intake.logs.datadoghq.com', 'ddproxy.rustaml.workers.dev');
  }
  return originalFetch.call(this, url, options);
};

// Option 2: Use DataDog SDK with proxy at infrastructure level
// Set up DNS/networking to redirect DataDog endpoints to your proxy

// Option 3: Fork DataDog SDK or wait for official proxy support
// DataDog doesn't officially support endpoint overrides