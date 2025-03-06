import * as k8s from '@kubernetes/client-node';

export const customResourceOperations = {
  /**
   * Get a ClientPod custom resource
   */
  async getClientPod(this: any, name: string) {
    try {
      const response = await this.customApi.getNamespacedCustomObject({
        group: 'gptme.ai',
        version: 'v1',
        namespace: this.namespace,
        plural: 'clientpods',
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
   * List all ClientPod resources in the namespace
   */
  async listClientPods(this: any) {
    try {
      const response = await this.customApi.listNamespacedCustomObject({
        group: 'gptme.ai',
        version: 'v1',
        namespace: this.namespace,
        plural: 'clientpods'
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  },

  /**
   * Create a new ClientPod resource
   */
  async createClientPod(this: any, clientPod: any) {
    try {
      const response = await this.customApi.createNamespacedCustomObject({
        group: 'gptme.ai',
        version: 'v1',
        namespace: this.namespace,
        plural: 'clientpods',
        body: clientPod
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  },

  /**
   * Update the status of a ClientPod
   */
  async updateClientPodStatus(this: any, name: string, status: any) {
    try {
      const response = await this.customApi.patchNamespacedCustomObjectStatus({
        group: 'gptme.ai',
        version: 'v1',
        namespace: this.namespace,
        plural: 'clientpods',
        name,
        body: {
          status
        }
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  },

  /**
   * Delete a ClientPod resource
   */
  async deleteClientPod(this: any, name: string) {
    try {
      const response = await this.customApi.deleteNamespacedCustomObject({
        group: 'gptme.ai',
        version: 'v1',
        namespace: this.namespace,
        plural: 'clientpods',
        name
      });
      return response.body;
    } catch (error) {
      throw error;
    }
  }
};
