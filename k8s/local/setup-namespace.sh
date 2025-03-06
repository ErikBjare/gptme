#!/bin/bash
set -e

NAMESPACE=${1:-gptmingdom}
ENV_FILE=${2:-.env}

echo "Setting up namespace: $NAMESPACE"

# Create namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
  echo "Creating namespace: $NAMESPACE"
  kubectl create namespace $NAMESPACE
else
  echo "Namespace $NAMESPACE already exists"
fi

# Set the current context to use the namespace
kubectl config set-context --current --namespace=$NAMESPACE

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE file not found"
  exit 1
fi

# Load environment variables from .env file
echo "Loading environment variables from $ENV_FILE"
export $(grep -v '^#' $ENV_FILE | xargs)

# Debug output
echo "DEBUG: ENV_FILE_ANTHROPIC_API_KEY is: ${ENV_FILE_ANTHROPIC_API_KEY:0:10}... (truncated for security)"
echo "DEBUG: ENV_FILE path: $(realpath $ENV_FILE)"
echo "DEBUG: ENV_FILE content: $(cat $ENV_FILE | sed 's/=.*$/=REDACTED/')"

# Create or update the secret
echo "Creating/updating secret: gptme-secrets"
kubectl create secret generic gptme-secrets \
  --from-literal=ENV_ANTHROPIC_API_KEY="$ENV_FILE_ANTHROPIC_API_KEY" \
  --namespace=$NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "Namespace and secrets have been set up successfully!"
echo "To deploy gptmingdom, run:"
echo "  skaffold dev -f k8s/local/skaffold.full.yaml --profile=dev -n $NAMESPACE"
