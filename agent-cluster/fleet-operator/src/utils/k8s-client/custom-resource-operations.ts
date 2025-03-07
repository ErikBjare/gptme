import * as k8s from "@kubernetes/client-node";
import { ClientPod, ClientPodStatus } from "../../models/types.js";
import logger from "../logger.js";
import { K8sClientContext } from "./k8s-client-types.js";

export const customResourceOperations = {
  /**
   * Get a ClientPod custom resource
   */
  async getClientPod(
    this: K8sClientContext,
    name: string,
  ): Promise<ClientPod | null> {
    try {
      const response = await this.customApi.getNamespacedCustomObject({
        group: "gptme.ai",
        version: "v1",
        namespace: this.namespace,
        plural: "clientpods",
        name,
      });
      logger.info(`Got ClientPod ${JSON.stringify(response)}`);
      return response;
    } catch (error) {
      // More robust error handling for 404 cases
      if (error && typeof error === "object") {
        // Check for different 404 patterns
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

      // Log the error structure to help debug
      logger.error("Error retrieving ClientPod:", error);
      throw error;
    }
  },

  /**
   * List all ClientPod resources in the namespace
   */
  async listClientPods(
    this: K8sClientContext,
  ): Promise<{ items: ClientPod[] }> {
    const response = await this.customApi.listNamespacedCustomObject({
      group: "gptme.ai",
      version: "v1",
      namespace: this.namespace,
      plural: "clientpods",
    });
    return response;
  },

  /**
   * Create a new ClientPod resource
   */
  async createClientPod(
    this: K8sClientContext,
    clientPod: ClientPod,
  ): Promise<ClientPod> {
    const response = await this.customApi.createNamespacedCustomObject({
      group: "gptme.ai",
      version: "v1",
      namespace: this.namespace,
      plural: "clientpods",
      body: clientPod,
    });
    return response;
  },

  /**
   * Update the status of a ClientPod
   */
  async updateClientPodStatus(
    this: K8sClientContext,
    name: string,
    status: Partial<ClientPodStatus>,
  ): Promise<ClientPod> {
    const response = await this.customApi.patchNamespacedCustomObjectStatus({
      group: "gptme.ai",
      version: "v1",
      namespace: this.namespace,
      plural: "clientpods",
      name,
      body: {
        status,
      },
    });
    return response;
  },

  /**
   * Delete a ClientPod resource
   */
  async deleteClientPod(
    this: K8sClientContext,
    name: string,
  ): Promise<k8s.V1Status> {
    const response = await this.customApi.deleteNamespacedCustomObject({
      group: "gptme.ai",
      version: "v1",
      namespace: this.namespace,
      plural: "clientpods",
      name,
    });
    return response;
  },
};
