import * as k8s from "@kubernetes/client-node";
import { ClientPodSpec } from "../../models/types.js";
import { ClientPodControllerContext } from "./controller-types.js";

/**
 * Create a pod manifest for a ClientPod
 */
export async function createPodManifest(
  this: ClientPodControllerContext,
  spec: ClientPodSpec,
  name: string,
): Promise<k8s.V1Pod> {
  // Default resource limits
  const cpu = spec.resources?.cpu || "100m";
  const memory = spec.resources?.memory || "256Mi";
  const model = spec.model || "default";

  // Get the image from running pods
  const image = await this.k8sClient.getGptmeServerImage();

  return {
    apiVersion: "v1",
    kind: "Pod",
    metadata: {
      name,
      namespace: this.namespace,
      labels: {
        app: this.podTemplate,
        "gptme.ai/client-id": spec.clientId,
        "gptme.ai/model": model,
      },
      annotations: {
        "gptme.ai/timeout": `${spec.timeout || 3600}`,
        "gptme.ai/last-activity": new Date().toISOString(),
      },
    },
    spec: {
      containers: [
        {
          name: "gptme-agent",
          // Use the image we discovered from running pods
          image: image,
          imagePullPolicy: "IfNotPresent",
          command: ["/scripts/startup.sh"],
          args: [
            "gptme-server",
            "--cors-origin=$(CORS_ORIGIN)",
            "--host=$(SERVER_HOST)",
            "--port=$(SERVER_PORT)",
          ],
          resources: {
            requests: {
              cpu,
              memory,
            },
            limits: {
              cpu,
              memory,
            },
          },
          env: [
            {
              name: "CLIENT_ID",
              value: spec.clientId,
            },
            // Removed MODEL environment variable to let the system auto-detect from API key
          ],
          envFrom: [
            {
              configMapRef: {
                name: "gptme-agent-config",
              },
            },
            {
              secretRef: {
                name: "gptme-agent-secrets",
              },
            },
          ],
          ports: [
            {
              containerPort: 5000,
              name: "http",
            },
          ],
          volumeMounts: [
            {
              name: "startup-script",
              mountPath: "/scripts",
              readOnly: true,
            },
          ],
          readinessProbe: {
            httpGet: {
              path: "/",
              port: 5000,
            },
            initialDelaySeconds: 10,
            periodSeconds: 5,
          },
          livenessProbe: {
            httpGet: {
              path: "/",
              port: 5000,
            },
            initialDelaySeconds: 15,
            periodSeconds: 20,
          },
        },
      ],
      volumes: [
        {
          name: "startup-script",
          configMap: {
            name: "gptme-startup-script",
            defaultMode: 493,  // 0755 in octal (rwxr-xr-x) - Makes script executable
          },
        },
      ],
      // Set termination grace period to 30 seconds
      terminationGracePeriodSeconds: 30,
    },
  };
}
