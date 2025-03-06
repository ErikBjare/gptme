import express, { NextFunction, Request, Response } from "express";
import { ClientPodController } from "../controllers/client-pod-controller/index.js";
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

    // Client request handler - specify route as string and handler as separate argument
    this.app.get(
      "/instance/:instanceId",
      async (req: Request, res: Response) => {
        try {
          const apiKey = req.header("X-API-Key");
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
          const clientPod = result as any;
          if (!clientPod.status || !clientPod.status.podName) {
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
    this.app.get("/admin/pods", async (req: Request, res: Response) => {
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
    });

    this.app.delete(
      "/admin/pods/:name",
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
