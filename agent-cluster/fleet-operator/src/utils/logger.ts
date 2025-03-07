import winston from "winston";

// Configure the Winston logger
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || "info",
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => {
      return `[${timestamp}] ${level.toUpperCase()}: ${message}`;
    }),
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.timestamp({
          format: "HH:mm:ss",
        }),
        winston.format.printf(
          ({ timestamp, level, message }) =>
            `[${timestamp}] ${level.toUpperCase()}: ${message}`,
        ),
      ),
    }),
  ],
});

export default logger;
