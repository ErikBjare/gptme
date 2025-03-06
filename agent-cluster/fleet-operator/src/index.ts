import dotenv from 'dotenv';
import { ClientPodController } from './controllers/client-pod-controller/index.js';
import { HttpServer } from './services/http-server.js';
import logger from './utils/logger.js';

// Load environment variables
dotenv.config();

// Create shutdown function
let shuttingDown = false;
let controller: ClientPodController | null = null;

async function shutdown(signal: string) {
  if (shuttingDown) return;
  shuttingDown = true;

  logger.info(`Received ${signal}, shutting down...`);

  // Stop the controller
  if (controller) {
    controller.stopWatching();
  }

  // Exit the process
  setTimeout(() => {
    logger.info('Exiting...');
    process.exit(0);
  }, 1000);
}

// Register shutdown handlers
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Main function
async function main() {
  try {
    logger.info('Starting GPTME Fleet Operator');

    // Create the controller
    controller = new ClientPodController();

    // Start watching for events
    await controller.startWatching();

    // Start the cleanup timer
    controller.startCleanupTimer();

    // Start HTTP server
    const httpPort = parseInt(process.env.HTTP_PORT || '8080');
    const server = new HttpServer(controller, httpPort);
    await server.start();

    logger.info('Fleet Operator is ready');
  } catch (error) {
    logger.error(`Failed to start Fleet Operator: ${error}`);
    process.exit(1);
  }
}

// Start the application
main().catch(err => {
  logger.error(`Unhandled error: ${err}`);
  process.exit(1);
});
