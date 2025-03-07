import express, { NextFunction, Request, Response } from "express";
import { ClientPodController } from "../controllers/client-pod-controller/index.js";
import { ClientPod } from "../models/types.js";
import logger from "../utils/logger.js";

export class HttpServer {
  private app: express.Application;
  private clientPodController: ClientPodController;
  private port: number;

  constructor(clientPodController: ClientPodController, port: number = 8080) {
    this.app = express();
    this.clientPodController = clientPodController;
    this.port = port;

    this.setupMiddleware();
    this.setupRoutes();
  }

  private setupMiddleware() {
    this.app.use(express.json());

    // Request logging middleware
    this.app.use((req: Request, res: Response, next: NextFunction) => {
      logger.info(`${req.method} ${req.path}`);
      next();
    });
  }

  private setupRoutes() {
    // Health check endpoints
    this.app.get("/healthz", (req: Request, res: Response) => {
      res.status(200).send("OK");
    });

    this.app.get("/readyz", (req: Request, res: Response) => {
      res.status(200).send("Ready");
    });

    // Traefik forwardAuth route for direct pod routing
    this.app.all("/api/route", async (req: Request, res: Response) => {
      logger.info("⭐⭐⭐ /api/route endpoint called ⭐⭐⭐");
      // Log all request headers to debug what Traefik is sending
      logger.info(`Request headers: ${JSON.stringify(req.headers, null, 2)}`);
      logger.info(`Request path: ${JSON.stringify(req.path)}`);

      try {
        // Extract API key from the original URL path
        // The path pattern is /api/v1/{apiKey}/instance/{instanceId}
        const originalPath = req.get("X-Forwarded-Uri") || req.path;
        const pathParts = originalPath.split("/");

        if (pathParts.length < 4) {
          logger.error(`Invalid path format: ${originalPath}`);
          res.status(400).json({ error: "Invalid path format" });
          return;
        }

        // Extract client identifiers from path
        const apiKey = pathParts[3];
        const instanceId = pathParts.length >= 6 ? pathParts[5] : "default";

        if (!apiKey) {
          res.status(401).json({ error: "API key is required" });
          return;
        }

        // Get or create client pod
        const clientPod = await this.clientPodController.handleClientRequest(
          apiKey,
          instanceId,
        );

        // Use the updated pod status for checking
        if (
          !clientPod?.status?.phase ||
          clientPod.status.phase !== "Running" ||
          !clientPod?.status?.podName
        ) {
          // Pod is still being created
          res.setHeader("Retry-After", "5");
          res.status(202).json({
            message: "Pod is being provisioned",
            status: clientPod?.status?.phase || "Creating",
          });
          return;
        }

        //        const clientId = this.clientPodController.generateClientId(
        //          apiKey,
        //          instanceId,
        //        );

        const podName = clientPod.status.podName;
        //const podServiceUrl = `http://agents.gptme.localhost/api/v1/${apiKey}/agents/${podName}`;
        const podServiceUrl = `http://agents.gptme.localhost/agents/${podName}`;
        //const podServiceUrl = `http://${serviceName}.${this.clientPodController.namespace}.svc.cluster.local:5000`;

        logger.info(`Redirecting to pod: ${podServiceUrl}`);

        // HTTP 307 maintains the original method (GET, POST, etc.)
        res.redirect(307, podServiceUrl);
      } catch (error) {
        logger.error(`Error handling route request: ${error}`);
        res.status(500).json({ error: "Internal server error" });
      }
    });

    // Client request handler - specify route as string and handler as separate argument
    this.app.get(
      "/api/v1/:apiKey/instances/:instanceId",
      async (req: Request, res: Response) => {
        try {
          const apiKey = req.params.apiKey;
          if (!apiKey) {
            res.status(401).json({ error: "API key is required" });
            return;
          }

          const instanceId = req.params.instanceId;
          const result = await this.clientPodController.handleClientRequest(
            apiKey,
            instanceId,
          );

          // Return the pod details that the client should connect to
          const clientPod = result as ClientPod;
          if (!clientPod?.status || !clientPod?.status?.podName) {
            res.status(202).json({
              message: "Pod is being provisioned",
              status: clientPod.status?.phase || "Creating",
            });
            return;
          }

          // Return pod connection details
          res.status(200).json({
            podName: clientPod.status.podName,
            status: clientPod.status.phase,
            clientId: clientPod.spec.clientId,
          });
          return;
        } catch (error) {
          logger.error(`Error handling client request: ${error}`);
          res.status(500).json({ error: "Internal server error" });
          return;
        }
      },
    );

    // Admin endpoints for managing client pods
    this.app.get(
      "/api/v1/:apiKey/admin/pods",
      async (req: Request, res: Response) => {
        try {
          const k8sClient = this.clientPodController["k8sClient"];
          const clientPods = await k8sClient.listClientPods();
          res.json(clientPods);
          return;
        } catch (error) {
          logger.error(`Error listing client pods: ${error}`);
          res.status(500).json({ error: "Internal server error" });
          return;
        }
      },
    );

    this.app.delete(
      "/api/v1/:apiKey/admin/pods/:name",
      async (req: Request, res: Response) => {
        try {
          const k8sClient = this.clientPodController["k8sClient"];
          await k8sClient.deleteClientPod(req.params.name);
          res.status(204).send();
          return;
        } catch (error) {
          logger.error(`Error deleting client pod: ${error}`);
          res.status(500).json({ error: "Internal server error" });
          return;
        }
      },
    );
  }

  start() {
    return new Promise<void>((resolve) => {
      this.app.listen(this.port, () => {
        logger.info(`HTTP server listening on port ${this.port}`);
        resolve();
      });
    });
  }
}
