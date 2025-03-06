import * as k8s from '@kubernetes/client-node';

export const podOperations = {
  /**
   * Create a new Pod
   */
  async createPod(this: any, pod: k8s.V1Pod) {
    try {
      const response = await this.k8sApi.createNamespacedPod({
        namespace: this.namespace,
        body: pod
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  },

  /**
   * Get a Pod by name
   */
  async getPod(this: any, name: string) {
    try {
      const response = await this.k8sApi.readNamespacedPod({
        namespace: this.namespace,
        name
      });
      return response.body;
    } catch (error: any) {
      if (error.response && error.response.statusCode === 404) {
        return null;
      }
      throw error;
    }
  },

  /**
   * Delete a Pod by name
   */
  async deletePod(this: any, name: string) {
    try {
      const response = await this.k8sApi.deleteNamespacedPod({
        namespace: this.namespace,
        name
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  }
};
