# Fleet Operator for GPTME

A Kubernetes operator that manages client-specific GPTME pods dynamically.

## Features

- Dynamic pod provisioning for clients
- Pod lifecycle management with automatic cleanup
- Client request routing through Traefik API Gateway
- Resource limiting for client pods

## Architecture

### Direct Pod Routing

The latest implementation uses Traefik to directly route client requests to their dedicated pods:

1. Client makes request to `/api/v1/{apiKey}/instance/{instanceId}`
2. Traefik middleware forwards request to Fleet Operator's `/api/route` endpoint
3. Fleet Operator checks if a pod exists for this client:
   - If yes: Returns routing headers to Traefik
   - If no: Creates a new pod and returns a status indicating the pod is being created
4. Based on the returned headers, Traefik routes the request directly to the client pod
5. Client receives response directly from their pod

This approach eliminates the need for clients to make a separate connection request after pod provisioning.

## Setup

### Prerequisites

- Kubernetes cluster
- Traefik installed as ingress controller
- `kubectl` configured to access your cluster

### Configuration

1. Apply Traefik middleware for routing:

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: fleet-router
  namespace: gptmingdom
spec:
  forwardAuth:
    address: http://fleet-operator.gptmingdom.svc.cluster.local:8080/api/route
    authResponseHeaders:
      - X-Pod-Service
      - X-Pod-Namespace
      - X-Pod-Port
    trustForwardHeader: true
```

2. Configure IngressRoute with the middleware:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: api-routes
  namespace: gptmingdom
spec:
  entryPoints:
    - web
  routes:
    - match: PathPrefix(`/api/v1`)
      kind: Rule
      middlewares:
        - name: fleet-router
      services:
        - name: fleet-operator
          port: 8080
```

## Testing

You can test the direct routing functionality with:

```bash
npm run test:routing
```

This will:
1. Make a request to the `/api/route` endpoint
2. Check for the proper routing headers
3. Verify the routing would work correctly

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Run linting
npm run lint
```
