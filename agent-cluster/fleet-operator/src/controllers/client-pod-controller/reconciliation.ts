import { ClientPod, ClientPodStatus } from "../../models/types.js";
import logger from "../../utils/logger.js";
import { ClientPodController } from "./index.js";

/**
 * Main reconciliation logic for ClientPod resources
 */
export async function reconcileClientPod(
  this: ClientPodController,
  clientPod: ClientPod,
) {
  if (!clientPod) {
    throw new Error("FATAL: reconcileClientPod called without a ClientPod");
  }
  const name = clientPod.metadata.name;
  const spec = clientPod.spec;
  const status = clientPod.status || {};

  // Check if pod already exists
  const podName = status.podName || `${this.podTemplate}-${spec.clientId}`;
  const existingPod = await this.k8sClient.getPod(podName);

  if (!existingPod) {
    // Pod doesn't exist, create it
    logger.info(`Creating pod for ClientPod ${name}`);
    const pod = await this.createPodManifest(spec, podName);
    await this.k8sClient.createPod(pod);

    // Update status
    await this.updateClientPodStatus(name, {
      podName,
      phase: "Creating",
      lastActivity: new Date().toISOString(),
    });
  } else {
    // Pod exists, check if it needs updating
    logger.info(`Pod ${podName} already exists for ClientPod ${name}`);

    // Update status with current pod phase
    await this.updateClientPodStatus(name, {
      podName,
      phase: existingPod.status?.phase || "Unknown",
      lastActivity: new Date().toISOString(),
    });
  }
}

/**
 * Clean up resources when a ClientPod is deleted
 */
export async function cleanupClientPodResources(
  this: ClientPodController,
  clientPod: ClientPod,
) {
  const status = clientPod.status;
  if (status?.podName) {
    try {
      logger.info(`Deleting pod ${status.podName}`);
      await this.k8sClient.deletePod(status.podName);
    } catch (error) {
      logger.error(`Error deleting pod ${status.podName}: ${error}`);
    }
  }
}

/**
 * Update the status of a ClientPod
 */
export async function updateClientPodStatus(
  this: ClientPodController,
  name: string,
  status: Partial<ClientPodStatus>,
) {
  try {
    const clientPod = (await this.k8sClient.getClientPod(name)) as ClientPod;
    if (!clientPod) {
      logger.warn(`ClientPod ${name} not found, cannot update status`);
      return null;
    }
    const currentStatus = clientPod.status || {};
    const phaseDiff =
      status.phase !== currentStatus.phase
        ? `${clientPod.spec.clientId}: ${currentStatus.phase} -> ${status.phase})`
        : "";
    const needsUpdate =
      phaseDiff ||
      !currentStatus.lastActivity ||
      new Date().getTime() - new Date(currentStatus.lastActivity).getTime() >
        60_000;

    if (!needsUpdate) {
      return clientPod;
    }

    if (phaseDiff) {
      logger.info(`Updating status for ClientPod ${name}: ${phaseDiff}`);
    }

    const response =
      await this.k8sClient.customApi.patchNamespacedCustomObjectStatus({
        group: "gptme.ai",
        version: "v1",
        namespace: this.namespace,
        plural: "clientpods",
        name,
        body: [
          {
            op: "replace",
            path: "/status",
            value: status,
          },
        ],
      });
    return response.body;
  } catch (error) {
    logger.error(`Error updating ClientPod status: ${error}`);
    throw error;
  }
}
