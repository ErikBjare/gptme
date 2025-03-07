import * as k8s from "@kubernetes/client-node";
import { K8sClientContext } from "./k8s-client-types.js";

export const serviceOperations = {
  /**
   * Create a new Service
   */
  async createService(
    this: K8sClientContext,
    service: k8s.V1Service,
  ): Promise<k8s.V1Service> {
    const response = await this.k8sApi.createNamespacedService({
      namespace: this.namespace,
      body: service,
    });
    return response;
  },

  /**
   * Delete a Service by name
   */
  async deleteService(
    this: K8sClientContext,
    name: string,
  ): Promise<k8s.V1ServiceStatus> {
    const response = await this.k8sApi.deleteNamespacedService({
      namespace: this.namespace,
      name,
    });
    if (!response.status) {
      throw new Error(`Failed to delete service ${name}`);
    }
    return response.status;
  },
};
