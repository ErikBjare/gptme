# Kubernetes Setup for gptme

This directory contains Kubernetes manifests for deploying gptme.

## Directory Structure

- `local/` - Contains configurations for local development
  - `gptme/` - Contains Kubernetes manifests for the gptme application
  - `skaffold.full.yaml` - Skaffold configuration for building and deploying
  - `setup-namespace.sh` - Script to set up namespace and secrets

## Components

1. **Deployment** - Runs the gptme-server container
2. **Service** - Exposes the gptme-server on port 8080
3. **ConfigMap** - Stores configuration values
4. **Secret** - Stores the ANTHROPIC_API_KEY securely
5. **Startup Script** - Generates the config.toml file with the API key
6. **Ingress** - Provides external access to the application

## Local Development

Pre-requisites:

```bash
# macOS
brew install skaffold kubectl minikube helm k9s
```

To run gptme locally with Kubernetes:

1. Make sure you have a Kubernetes cluster running (minikube, kind, k3d, etc.)
2. Create a `.env` file in the repository root with your API key:
   ```bash
   ANTHROPIC_API_KEY=your_api_key_here
   ```

3. Run the setup script to create the namespace and secrets:
   ```bash
   cd /path/to/gptme
   ./k8s/local/setup-namespace.sh gptmingdom
   ```

4. Deploy with Skaffold:
   ```bash
   skaffold dev -f k8s/local/skaffold.full.yaml --profile=dev
   ```

This will:
- Build the Docker image
- Deploy the application to your Kubernetes cluster
- Set up port forwarding from localhost:8080 to the service
- Stream logs from the pods

## Accessing the Application

Once deployed, the application can be accessed:

1. Via port forwarding: http://localhost:8080
2. Via Ingress: http://gptme.localhost (requires adding an entry to your hosts file)

## Configuration

Configuration is handled through:
- Environment variables in `gptme-agent-config` ConfigMap
- Secrets in `gptme-agent-secrets`
- A generated config.toml file created by the startup script

The startup script automatically creates the config.toml file with the API key from the secret.
