# GPTME Fleet Operator

A Kubernetes operator that manages client-specific GPTME pods for the gptme.ai platform.

## Overview

The Fleet Operator dynamically provisions and manages dedicated GPTME pods for each unique client. It works in conjunction with a Traefik API Gateway to route client requests to their assigned pods.

## Features

- Client identification and pod assignment
- Dynamic pod provisioning based on client requests
- Automatic pod lifecycle management with timeout-based cleanup
- Resource limits and constraints
- API for client connections and admin operations

## Architecture

1. **Client Request Flow**:
   - Client makes request to `/api/v1/{apiKey}/instances/{instanceId}`
   - Traefik extracts the apiKey and adds it as X-API-Key header
   - Request is forwarded to the Fleet Operator
   - Operator creates/finds the ClientPod and returns connection details

2. **Components**:
   - **API Gateway**: Traefik for routing and client identification
   - **Fleet Operator**: This TypeScript application
   - **Custom Resources**: ClientPod CRD

## Development

### Prerequisites

- Node.js 20+
- Kubernetes cluster (or minikube/kind for local development)
- kubectl configured to connect to your cluster

### Setup

```bash
# Install dependencies
npm install

# Start in development mode
npm run dev
```

### Build

```bash
# Build TypeScript
npm run build

# Build Docker image
docker build -t fleet-operator:latest .
```

## Deployment

The operator is deployed via Kubernetes manifests in the `k8s/local/fleet-operator` directory.

```bash
# Apply the manifests
kubectl apply -f k8s/local/fleet-operator/
```

## API Reference

### Client API

- `GET /instances/:instanceId` - Get or create a client pod
  - Headers: `X-API-Key` (required)
  - Response: Pod connection details

### Admin API

- `GET /admin/pods` - List all client pods
- `DELETE /admin/pods/:name` - Delete a client pod

## Environment Variables

- `NAMESPACE` - Kubernetes namespace (default: from service account)
- `POD_TEMPLATE` - Pod template name (default: 'gptme-client')
- `LOG_LEVEL` - Logging level (default: 'info')
- `HTTP_PORT` - HTTP server port (default: 8080)
