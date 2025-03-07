import { ClientPod } from "../../models/types.js";
import logger from "../../utils/logger.js";
import { ClientPodController } from "./index.js";

/**
 * Cleanup inactive pods based on timeout
 */
export async function cleanupInactivePods(this: ClientPodController) {
  try {
    const clientPodList = (await this.k8sClient.listClientPods()) as {
      items: ClientPod[];
    };
    const now = new Date();

    for (const clientPod of clientPodList.items) {
      if (!clientPod?.status?.lastActivity) continue;

      const lastActivity = new Date(clientPod.status.lastActivity);
      const timeoutSeconds = clientPod.spec.timeout || 3600;
      const elapsedSeconds = (now.getTime() - lastActivity.getTime()) / 1000;

      if (elapsedSeconds > timeoutSeconds) {
        logger.info(
          `ClientPod ${clientPod.metadata.name} has timed out, cleaning up`,
        );
        await this.k8sClient.deleteClientPod(clientPod.metadata.name);
      }
    }
  } catch (error) {
    logger.error(`Error cleaning up inactive pods: ${error}`);
  }
}

/**
 * Start the inactivity cleanup timer
 */
export function startCleanupTimer(
  this: ClientPodController,
  intervalMinutes: number = 5,
) {
  // Run cleanup every intervalMinutes
  setInterval(
    () => {
      this.cleanupInactivePods().catch((err: Error) => {
        logger.error(`Cleanup timer error: ${err}`);
      });
    },
    intervalMinutes * 60 * 1000,
  );

  logger.info(`Started cleanup timer with interval ${intervalMinutes} minutes`);
}
