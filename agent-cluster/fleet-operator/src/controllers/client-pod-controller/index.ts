import * as k8s from "@kubernetes/client-node";
import { ClientPod, ClientPodStatus } from "../../models/types.js";
import { KubernetesClient } from "../../utils/k8s-client.js";
import { cleanupInactivePods, startCleanupTimer } from "./cleanup.js";
import { generateClientId, handleClientRequest } from "./client-management.js";
import { setupWatchers, stopWatching } from "./event-handlers.js";
import { createPodManifest } from "./pod-management.js";
import {
  cleanupClientPodResources,
  reconcileClientPod,
  updateClientPodStatus,
} from "./reconciliation.js";

export class ClientPodController {
  private k8sClient: KubernetesClient;
  private namespace: string;
  private podTemplate: string;
  private informer: k8s.Informer<ClientPod>;
  private watchEnabled: boolean = false;

  constructor() {
    this.namespace = process.env.NAMESPACE || "default";
    this.podTemplate = process.env.POD_TEMPLATE || "gptme-client";
    this.k8sClient = new KubernetesClient(this.namespace);

    // Initialize the informer to watch ClientPod resources
    const kc = new k8s.KubeConfig();
    kc.loadFromDefault();

    const customObjectsApi = kc.makeApiClient(k8s.CustomObjectsApi);

    this.informer = k8s.makeInformer(
      kc,
      `/apis/gptme.ai/v1/namespaces/${this.namespace}/clientpods`,
      () =>
        customObjectsApi.listNamespacedCustomObject({
          group: "gptme.ai",
          version: "v1",
          namespace: this.namespace,
          plural: "clientpods",
        }) as any,
    );
  }

  // Event handling
  async startWatching() {
    return setupWatchers.call(this);
  }

  stopWatching() {
    return stopWatching.call(this);
  }

  // Reconciliation
  async reconcileClientPod(clientPod: ClientPod) {
    return reconcileClientPod.call(this, clientPod);
  }

  async cleanupClientPodResources(clientPod: ClientPod) {
    return cleanupClientPodResources.call(this, clientPod);
  }

  async updateClientPodStatus(name: string, status: Partial<ClientPodStatus>) {
    return updateClientPodStatus.call(this, name, status);
  }

  // Pod creation
  createPodManifest(spec: any, name: string): k8s.V1Pod {
    return createPodManifest.call(this, spec, name);
  }

  // Client management
  async handleClientRequest(apiKey: string, instanceId: string) {
    return handleClientRequest.call(this, apiKey, instanceId);
  }

  generateClientId(apiKey: string, instanceId: string): string {
    return generateClientId.call(this, apiKey, instanceId);
  }

  // Cleanup
  async cleanupInactivePods() {
    return cleanupInactivePods.call(this);
  }

  startCleanupTimer(intervalMinutes: number = 5) {
    return startCleanupTimer.call(this, intervalMinutes);
  }
}
