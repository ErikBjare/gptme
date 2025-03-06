import * as k8s from '@kubernetes/client-node';

/**
 * Create a pod manifest for a ClientPod
 */
export function createPodManifest(this: any, spec: any, name: string): k8s.V1Pod {
  // Default resource limits
  const cpu = spec.resources?.cpu || '100m';
  const memory = spec.resources?.memory || '256Mi';
  const model = spec.model || 'default';

  return {
    apiVersion: 'v1',
    kind: 'Pod',
    metadata: {
      name,
      namespace: this.namespace,
      labels: {
        app: this.podTemplate,
        'gptme.ai/client-id': spec.clientId,
        'gptme.ai/model': model,
      },
      annotations: {
        'gptme.ai/timeout': `${spec.timeout || 3600}`,
        'gptme.ai/last-activity': new Date().toISOString(),
      }
    },
    spec: {
      containers: [
        {
          name: 'gptme',
          image: 'gptme:latest',
          resources: {
            requests: {
              cpu,
              memory,
            },
            limits: {
              cpu,
              memory,
            }
          },
          env: [
            {
              name: 'CLIENT_ID',
              value: spec.clientId,
            },
            {
              name: 'MODEL',
              value: model,
            }
          ],
          ports: [
            {
              containerPort: 8080,
              name: 'http',
            }
          ]
        }
      ],
      // Set termination grace period to 30 seconds
      terminationGracePeriodSeconds: 30,
    }
  };
}
