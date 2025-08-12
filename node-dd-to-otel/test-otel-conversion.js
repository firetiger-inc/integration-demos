#!/usr/bin/env node

/**
 * Test OTEL conversion logic locally
 * This simulates the DataDog to OTEL conversion that happens in the worker
 */

// Simulate the conversion function from the worker
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

// Test with sample DataDog payloads
console.log('🧪 Testing DataDog to OTEL conversion...\n');

// Test 1: Simple log
console.log('📋 Test 1: Simple DataDog log');
const simpleLog = JSON.stringify({
  logs: [{
    message: 'User clicked extension icon',
    level: 'info',
    timestamp: '2024-01-15T10:30:00.000Z',
    service: 'browser-extension',
    env: 'production',
    version: '2.1.0',
    action: 'icon_click',
    sessionId: 'session_abc123'
  }]
});

const otelResult1 = convertDataDogToOTEL(simpleLog, 'test-123');
console.log('✅ OTEL Output:');
console.log(JSON.stringify(otelResult1, null, 2));
console.log('\n' + '='.repeat(80) + '\n');

// Test 2: Error log with stack trace
console.log('📋 Test 2: DataDog error log');
const errorLog = JSON.stringify({
  logs: [{
    message: 'Network request failed in content script',
    level: 'error',
    timestamp: '2024-01-15T10:31:00.000Z',
    service: 'browser-extension',
    env: 'production',
    error: {
      name: 'NetworkError',
      message: 'Failed to fetch',
      stack: 'NetworkError: Failed to fetch\n    at fetch (/content.js:123:5)'
    },
    errorCode: 'NETWORK_ERROR',
    endpoint: 'https://api.example.com/data',
    retryCount: 3
  }]
});

const otelResult2 = convertDataDogToOTEL(errorLog, 'test-456');
console.log('✅ OTEL Output:');
console.log(JSON.stringify(otelResult2, null, 2));
console.log('\n' + '='.repeat(80) + '\n');

// Test 3: Multiple logs in single payload
console.log('📋 Test 3: Multiple DataDog logs');
const multiLogs = JSON.stringify({
  logs: [
    {
      message: 'Extension initialized',
      level: 'info',
      timestamp: '2024-01-15T10:29:00.000Z',
      service: 'browser-extension',
      startup: true
    },
    {
      message: 'Performance warning detected',
      level: 'warn',
      timestamp: '2024-01-15T10:29:30.000Z',
      service: 'browser-extension',
      loadTime: 2500,
      component: 'content-script'
    }
  ]
});

const otelResult3 = convertDataDogToOTEL(multiLogs, 'test-789');
console.log('✅ OTEL Output:');
console.log(JSON.stringify(otelResult3, null, 2));
console.log('\n' + '='.repeat(80) + '\n');

console.log('🎉 All conversion tests completed!');