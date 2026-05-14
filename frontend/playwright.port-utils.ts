import { execFileSync } from "node:child_process";

function findOpenPort(fallbackPort: string): string {
  try {
    const script = `
      const net = require("node:net");
      const server = net.createServer();
      server.listen(0, "127.0.0.1", () => {
        const address = server.address();
        process.stdout.write(String(typeof address === "object" && address ? address.port : ""));
        server.close();
      });
      server.on("error", () => process.exit(1));
    `;
    const output = execFileSync(process.execPath, ["-e", script], { encoding: "utf-8" }).trim();
    return output || fallbackPort;
  } catch {
    return fallbackPort;
  }
}

export function resolvePort(envName: string, fallbackPort: string): string {
  const explicit = process.env[envName]?.trim();
  if (explicit) {
    return explicit;
  }
  const port = findOpenPort(fallbackPort);
  process.env[envName] = port;
  return port;
}
