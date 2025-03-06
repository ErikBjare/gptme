import { ClientPod, ClientPodStatus } from '../../models/types.js';
import logger from '../../utils/logger.js';

/**
 * Main reconciliation logic for ClientPod resources
 */
export async function reconcileClientPod(this: any, clientPod: ClientPod) {
  const name = clientPod.metadata.name;
  const spec = clientPod.spec;
  const status = clientPod.status || {};

  // Check if pod already exists
  const podName = status.podName || `${this.podTemplate}-${spec.clientId}`;
  const existingPod = await this.k8sClient.getPod(podName);

  if (!existingPod) {
    // Pod doesn't exist, create it
    logger.info(`Creating pod for ClientPod ${name}`);
    const pod = this.createPodManifest(spec, podName);
    await this.k8sClient.createPod(pod);

    // Update status
    await this.updateClientPodStatus(name, {
      podName,
      phase: 'Creating',
      lastActivity: new Date().toISOString()
    });
  } else {
    // Pod exists, check if it needs updating
    logger.info(`Pod ${podName} already exists for ClientPod ${name}`);

    // Update status with current pod phase
    await this.updateClientPodStatus(name, {
      podName,
      phase: existingPod.status?.phase || 'Unknown',
      lastActivity: new Date().toISOString()
    });
  }
}

/**
 * Clean up resources when a ClientPod is deleted
 */
export async function cleanupClientPodResources(this: any, clientPod: ClientPod) {
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
export async function updateClientPodStatus(this: any, name: string, status: Partial<ClientPodStatus>) {
  try {
    const clientPod = await this.k8sClient.getClientPod(name) as ClientPod;
    if (!clientPod) {
      logger.warn(`ClientPod ${name} not found, cannot update status`);
      return;
    }

    // Merge the existing status with the new status
    const newStatus = {
      ...(clientPod.status || {}),
      ...status
    };

    await this.k8sClient.updateClientPodStatus(name, newStatus);
  } catch (error) {
    logger.error(`Error updating ClientPod status: ${error}`);
  }
}
