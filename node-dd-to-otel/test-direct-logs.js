import fetch from 'node-fetch';
import { config } from 'dotenv';

config();

const DD_CLIENT_TOKEN = process.env.DD_CLIENT_TOKEN;
const DD_SITE = process.env.DD_SITE || 'us5.datadoghq.com';

async function testDirectDataDogLogs() {
  const endpoint = `https://http-intake.logs.${DD_SITE}/v1/input/${DD_CLIENT_TOKEN}`;
  
  const logData = [{
    message: "Test log from Node.js direct HTTP",
    level: "info",
    timestamp: new Date().toISOString(),
    service: "test-app",
    env: "prod",
    version: "1.0.0",
    ddsource: "browser",
    hostname: "test-simulation"
  }];
  
  console.log(`🌐 Testing direct DataDog endpoint: ${endpoint}`);
  console.log(`📤 Sending log data:`, JSON.stringify(logData, null, 2));
  
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Node.js Test Client/1.0.0'
      },
      body: JSON.stringify(logData)
    });
    
    const responseText = await response.text();
    
    console.log(`✅ Response Status: ${response.status} ${response.statusText}`);
    console.log(`📥 Response Body: ${responseText}`);
    
    if (response.ok) {
      console.log(`🎉 SUCCESS: Log sent to DataDog successfully!`);
      console.log(`💡 Check your DataDog logs dashboard for the test log`);
    } else {
      console.log(`❌ FAILED: ${response.status} - ${responseText}`);
    }
    
  } catch (error) {
    console.log(`💥 ERROR: ${error.message}`);
  }
}

testDirectDataDogLogs();