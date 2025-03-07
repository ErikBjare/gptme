import * as k8s from "@kubernetes/client-node";
import logger from "../logger.js";
import { KubernetesClient } from "./index.js";
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

  /**
   * List Pods by label selector
   */
  async listPodsByLabel(
    this: K8sClientContext,
    labelSelector: string,
  ): Promise<k8s.V1Pod[]> {
    try {
      const response = await this.k8sApi.listNamespacedPod({
        namespace: this.namespace,
        labelSelector,
      });
      return response.items;
    } catch (error) {
      logger.error("Error in listPodsByLabel:", error);
      throw error;
    }
  },

  /**
   * Get the current GPTME server image from running pods
   */
  async getGptmeServerImage(this: KubernetesClient): Promise<string> {
    try {
      // Look for pods with the label from the working deployment
      const pods = await this.listPodsByLabel("app=gptme-agent-label");

      // If we found any pods, use the image from the first one
      if (
        pods.length > 0 &&
        pods[0].spec?.containers &&
        pods[0].spec.containers.length > 0
      ) {
        const image = pods[0].spec.containers[0].image;
        if (!image) {
          throw new Error("No image found in pod spec");
        }
        logger.info(`Found GPTME server image from running pod: ${image}`);
        return image;
      }

      // Fallback to default
      logger.warn("No running GPTME server pods found, using fallback image");
      return "gptme-server:latest";
    } catch (error) {
      logger.error("Error getting GPTME server image:", error);
      // Fallback to default
      return "gptme-server:latest";
    }
  },
};
