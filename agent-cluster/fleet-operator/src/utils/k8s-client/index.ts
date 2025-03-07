import * as k8s from "@kubernetes/client-node";
import { customResourceOperations } from "./custom-resource-operations.js";
import { K8sClientContext } from "./k8s-client-types.js";
import { podOperations } from "./pod-operations.js";
import { serviceOperations } from "./service-operations.js";

/**
 * Kubernetes client wrapper for interacting with the Kubernetes API
 */
export class KubernetesClient implements K8sClientContext {
  public k8sApi: k8s.CoreV1Api;
  public customApi: k8s.CustomObjectsApi;
  public namespace: string;

  // Mix in the operations
  public createPod: typeof podOperations.createPod;
  public getPod: typeof podOperations.getPod;
  public deletePod: typeof podOperations.deletePod;

  public createService: typeof serviceOperations.createService;
  public deleteService: typeof serviceOperations.deleteService;

  public getClientPod: typeof customResourceOperations.getClientPod;
  public listClientPods: typeof customResourceOperations.listClientPods;
  public createClientPod: typeof customResourceOperations.createClientPod;
  public updateClientPodStatus: typeof customResourceOperations.updateClientPodStatus;
  public deleteClientPod: typeof customResourceOperations.deleteClientPod;

  constructor(namespace: string = process.env.NAMESPACE || "default") {
    const kc = new k8s.KubeConfig();
    kc.loadFromDefault();

    this.k8sApi = kc.makeApiClient(k8s.CoreV1Api);
    this.customApi = kc.makeApiClient(k8s.CustomObjectsApi);
    this.namespace = namespace;

    this.createPod = podOperations.createPod.bind(this);
    this.getPod = podOperations.getPod.bind(this);
    this.deletePod = podOperations.deletePod.bind(this);

    // Bind service operations
    this.createService = serviceOperations.createService.bind(this);
    this.deleteService = serviceOperations.deleteService.bind(this);

    // Bind custom resource operations
    this.getClientPod = customResourceOperations.getClientPod.bind(this);
    this.listClientPods = customResourceOperations.listClientPods.bind(this);
    this.createClientPod = customResourceOperations.createClientPod.bind(this);
    this.updateClientPodStatus =
      customResourceOperations.updateClientPodStatus.bind(this);
    this.deleteClientPod = customResourceOperations.deleteClientPod.bind(this);
  }
}
