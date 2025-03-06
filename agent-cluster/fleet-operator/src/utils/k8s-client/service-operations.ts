import * as k8s from '@kubernetes/client-node';

export const serviceOperations = {
  /**
   * Create a new Service
   */
  async createService(this: any, service: k8s.V1Service) {
    try {
      const response = await this.k8sApi.createNamespacedService({
        namespace: this.namespace,
        body: service
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  },

  /**
   * Delete a Service by name
   */
  async deleteService(this: any, name: string) {
    try {
      const response = await this.k8sApi.deleteNamespacedService({
        namespace: this.namespace,
        name
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  }
};
