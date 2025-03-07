import * as k8s from "@kubernetes/client-node";
import logger from "../logger.js";
import { K8sClientContext } from "./k8s-client-types.js";

export const podOperations = {
  /**
   * Create a new Pod
   */
  async createPod(
    this: K8sClientContext,
    pod: k8s.V1Pod,
  ): Promise<k8s.V1Pod | void> {
    try {
      const response = await this.k8sApi.createNamespacedPod({
        namespace: this.namespace,
        body: pod,
      });
      return response;
    } catch (error) {
      // Type the error object properly
      if (
        error &&
        typeof error === "object" &&
        "code" in error &&
        error.code === 409
      ) {
        logger.info(`Pod ${pod.metadata?.name} already exists`);
        return;
      }
      throw error;
    }
  },

  /**
   * Get a Pod by name
   */
  async getPod(
    this: K8sClientContext,
    name: string,
  ): Promise<k8s.V1Pod | null> {
    try {
      const response = await this.k8sApi.readNamespacedPod({
        namespace: this.namespace,
        name,
      });
      return response;
    } catch (error) {
      // Type the error object properly
      if (error && typeof error === "object") {
        const errorObj = error as {
          response?: { statusCode?: number };
          statusCode?: number;
          code?: number;
          message?: string;
        };

        if (
          (errorObj.response && errorObj.response.statusCode === 404) ||
          errorObj.statusCode === 404 ||
          errorObj.code === 404 ||
          (errorObj.message && errorObj.message.includes("not found"))
        ) {
          return null;
        }
      }

      // Use logger instead of console
      logger.error("Error in getPod:", error);
      throw error;
    }
  },

  /**
   * Delete a Pod by name
   */
  async deletePod(this: K8sClientContext, name: string): Promise<k8s.V1Status> {
    const response = await this.k8sApi.deleteNamespacedPod({
      namespace: this.namespace,
      name,
    });
    if (!response?.status) {
      throw new Error("No status in deletePod response");
    }
    return response.status;
  },
};
