import { KubernetesClient } from "../../utils/k8s-client/index.js";
import * as k8s from "@kubernetes/client-node";
import { ClientPod } from "../../models/types.js";

// This interface defines the shape of the controller that will be used as 'this'
export interface ClientPodControllerContext {
  k8sClient: KubernetesClient;
  namespace: string;
  podTemplate: string;
  informer: k8s.Informer<ClientPod>;
  watchEnabled: boolean;
}
