// Custom Resource Definitions

// ClientPod represents a client-specific pod managed by the operator
export interface ClientPod {
  apiVersion: string;
  kind: string;
  metadata: {
    name: string;
    namespace: string;
    [key: string]: any;
  };
  spec: ClientPodSpec;
  status?: ClientPodStatus;
}

// Specification for ClientPod
export interface ClientPodSpec {
  clientId: string;
  model?: string;
  resources?: {
    cpu?: string;
    memory?: string;
  };
  timeout?: number;
}

// Status of ClientPod
export interface ClientPodStatus {
  podName?: string;
  phase?: string;
  lastActivity?: string;
}

// List of ClientPods
export interface ClientPodList {
  apiVersion: string;
  kind: string;
  metadata: {
    continue?: string;
    resourceVersion?: string;
  };
  items: ClientPod[];
}
