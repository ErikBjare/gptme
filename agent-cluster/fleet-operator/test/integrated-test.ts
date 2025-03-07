import express, { Request, Response } from 'express';
import fetch from 'node-fetch';

// Create a mock server that simulates the Fleet Operator
async function startMockServer() {
  const app = express();
  const port = 8080;

  // Simulate the /api/route endpoint
  app.all('/api/route', async (req: Request, res: Response) => {
    try {
      // Extract API key from the original URL path
      const originalPath = req.get('X-Forwarded-Uri') || req.path;
      console.log(`Received request with X-Forwarded-Uri: ${originalPath}`);

      const pathParts = originalPath.split('/');

      if (pathParts.length < 4) {
        console.log(`Invalid path format: ${originalPath}`);
        res.status(400).json({ error: 'Invalid path format' });
        return;
      }

      // Extract client identifiers from path
      const apiKey = pathParts[3];
      const instanceId = pathParts.length >= 6 ? pathParts[5] : 'default';

      console.log(`Extracted apiKey: ${apiKey}, instanceId: ${instanceId}`);

      if (!apiKey) {
        res.status(401).json({ error: 'API key is required' });
        return;
      }

      // Simulate pod creation delay for testing
      if (apiKey === 'new-client') {
        // Simulate a pod that's still being created
        res.setHeader('Retry-After', '5');
        res.status(202).json({
          message: 'Pod is being provisioned',
          status: 'Creating',
        });
        return;
      }

      // Simulate a running pod
      const podName = `gptme-client-${apiKey}-${instanceId}`;

      // Set headers for Traefik routing
      res.setHeader('X-Pod-Service', podName);
      res.setHeader('X-Pod-Namespace', 'gptmingdom');
      res.setHeader('X-Pod-Port', '5000');

      // Authorize the request (200 OK)
      res.status(200).send('OK');
    } catch (error) {
      console.error(`Error handling route request: ${error}`);
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  // Start the server
  return new Promise<void>((resolve) => {
    const server = app.listen(port, () => {
      console.log(`Mock server listening on port ${port}`);
      resolve();
    });

    // Store the server so we can close it later
    // @ts-ignore
    global.mockServer = server;
  });
}

// Test client for checking Traefik routing
async function testTraefikRouting() {
  console.log('\nTesting existing client pod:');
  console.log('---------------------------');

  // Test with an existing client
  try {
    const response = await fetch('http://localhost:8080/api/route', {
      headers: {
        'X-Forwarded-Uri': '/api/v1/test-client/instance/123'
      }
    });

    console.log(`Status: ${response.status}`);

    // Log all headers
    console.log('Response headers:');
    response.headers.forEach((value, name) => {
      console.log(`  ${name}: ${value}`);
    });

    if (response.status === 200) {
      console.log('\nSuccess! Traefik would route directly to the pod.');

      // Check for expected headers
      const podService = response.headers.get('X-Pod-Service');
      const podNamespace = response.headers.get('X-Pod-Namespace');
      const podPort = response.headers.get('X-Pod-Port');

      console.log(`Pod Service: ${podService}`);
      console.log(`Pod Namespace: ${podNamespace}`);
      console.log(`Pod Port: ${podPort}`);

      if (podService && podNamespace && podPort) {
        console.log('All required routing headers are present. ✅');
      } else {
        console.log('ERROR: Some required routing headers are missing! ❌');
      }
    } else {
      console.log('Unexpected response:');
      const text = await response.text();
      console.log(text);
    }
  } catch (error) {
    console.error('Error testing Traefik routing:', error);
  }

  // Test with a new client (pod still being created)
  console.log('\nTesting new client pod creation:');
  console.log('-------------------------------');

  try {
    const response = await fetch('http://localhost:8080/api/route', {
      headers: {
        'X-Forwarded-Uri': '/api/v1/new-client/instance/456'
      }
    });

    console.log(`Status: ${response.status}`);

    // Log all headers
    console.log('Response headers:');
    response.headers.forEach((value, name) => {
      console.log(`  ${name}: ${value}`);
    });

    if (response.status === 202) {
      console.log('\nPod is still being created. Response body:');
      const data = await response.json();
      console.log(data);

      const retryAfter = response.headers.get('Retry-After');
      if (retryAfter) {
        console.log(`Retry-After header is present with value: ${retryAfter} ✅`);
      } else {
        console.log('ERROR: Retry-After header is missing! ❌');
      }
    } else {
      console.log('Unexpected response:');
      const text = await response.text();
      console.log(text);
    }
  } catch (error) {
    console.error('Error testing Traefik routing:', error);
  }

  // Close the server
  // @ts-ignore
  if (global.mockServer) {
    // @ts-ignore
    global.mockServer.close(() => {
      console.log('Mock server closed');
    });
  }
}

// Run the test
async function runIntegratedTest() {
  console.log('Starting integrated test for Traefik direct pod routing...');
  await startMockServer();
  await testTraefikRouting();
}

runIntegratedTest();
