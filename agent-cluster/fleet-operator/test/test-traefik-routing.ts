import fetch from 'node-fetch';

async function testTraefikRouting() {
  console.log('Testing Traefik direct pod routing...');

  // Test the /api/route endpoint
  try {
    const response = await fetch('http://localhost:8080/api/route', {
      headers: {
        'X-Forwarded-Uri': '/api/v1/test-api-key/instance/123'
      }
    });

    console.log(`Status: ${response.status}`);

    // Log all headers
    response.headers.forEach((value, name) => {
      console.log(`${name}: ${value}`);
    });

    if (response.status === 200) {
      console.log('Success! Traefik would route directly to the pod.');

      // Check for expected headers
      const podService = response.headers.get('X-Pod-Service');
      const podNamespace = response.headers.get('X-Pod-Namespace');
      const podPort = response.headers.get('X-Pod-Port');

      console.log(`Pod Service: ${podService}`);
      console.log(`Pod Namespace: ${podNamespace}`);
      console.log(`Pod Port: ${podPort}`);

      if (podService && podNamespace && podPort) {
        console.log('All required routing headers are present.');
      } else {
        console.log('ERROR: Some required routing headers are missing!');
      }
    } else if (response.status === 202) {
      console.log('Pod is still being created. Check the response:');
      const data = await response.json();
      console.log(data);
    } else {
      console.log('Unexpected response:');
      const text = await response.text();
      console.log(text);
    }
  } catch (error) {
    console.error('Error testing Traefik routing:', error);
  }
}

// Run the test
testTraefikRouting();
