import { ClientPod } from "../../models/types.js";
import logger from "../../utils/logger.js";
import { ClientPodController } from "./index.js";

export async function setupWatchers(this: ClientPodController) {
  if (this.watchEnabled) {
    return;
  }

  // Add event handlers
  this.informer.on("add", async (clientPod: ClientPod) => {
    try {
      logger.info(`ClientPod added: ${clientPod.metadata.name}`);
      await this.reconcileClientPod(clientPod);
    } catch (error) {
      // Use a more specific type than 'any'
      if ((error as { statusCode?: number }).statusCode === 409) {
        // Pod already exists
        logger.info(`ClientPod ${clientPod.metadata.name} already exists`);
        return;
      }
      logger.error(`Error handling ClientPod add: ${error}`);
    }
  });

  this.informer.on("update", async (clientPod: ClientPod) => {
    try {
      logger.info(`ClientPod updated: ${clientPod.metadata.name}`);
      await this.reconcileClientPod(clientPod);
    } catch (error) {
      logger.error(`Error handling ClientPod update: ${error}`);
    }
  });

  this.informer.on("delete", async (clientPod: ClientPod) => {
    try {
      logger.info(`ClientPod deleted: ${clientPod.metadata.name}`);
      await this.cleanupClientPodResources(clientPod);
    } catch (error) {
      logger.error(`Error handling ClientPod delete: ${error}`);
    }
  });

  // Use a more specific type for the error
  this.informer.on("error", (err: ClientPod) => {
    logger.error(`Informer error: ${err}`);
    // Attempt to restart the informer after a delay
    setTimeout(() => {
      if (this.watchEnabled) {
        logger.info("Attempting to restart informer...");
        this.informer.start();
      }
    }, 5000);
  });

  // Start the informer
  this.informer.start();
  this.watchEnabled = true;
  logger.info("Started watching ClientPod resources");
}

export function stopWatching(this: ClientPodController) {
  if (!this.watchEnabled) {
    return;
  }
  this.informer.stop();
  this.watchEnabled = false;
  logger.info("Stopped watching ClientPod resources");
}
