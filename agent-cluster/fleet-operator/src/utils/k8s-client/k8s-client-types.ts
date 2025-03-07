import * as k8s from "@kubernetes/client-node";

// Interface for the Kubernetes client context (used as 'this')
export interface K8sClientContext {
  namespace: string;
  k8sApi: k8s.CoreV1Api;
  customApi: k8s.CustomObjectsApi;
}
