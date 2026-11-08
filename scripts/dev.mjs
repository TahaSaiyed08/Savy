import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

if (!existsSync(resolve("apps/web/node_modules/next"))) {
  console.error("Web dependencies are missing. Run `dev.cmd setup` before `dev.cmd dev`.");
  process.exit(1);
}

if (!existsSync(resolve(".env"))) {
  console.error(".env is missing. Run `dev.cmd setup` before `dev.cmd dev`.");
  process.exit(1);
}

const windows = process.platform === "win32";
const children = new Set();
let stopping = false;
let exitCode = 0;

function stop(code) {
  if (stopping) return;
  stopping = true;
  exitCode = code;

  for (const child of children) {
    if (!child.pid) continue;
    if (windows) {
      const killer = spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
        stdio: "ignore",
      });
      killer.on("error", (error) => {
        console.error(`Failed to stop process ${child.pid}:`, error.message);
        process.exitCode = 1;
      });
      killer.on("exit", (status) => {
        if (status !== 0 && children.has(child)) {
          console.error(`Failed to stop process tree ${child.pid} (taskkill exit ${status}).`);
          process.exitCode = 1;
        }
      });
    } else {
      try {
        process.kill(-child.pid, "SIGTERM");
      } catch (error) {
        if (error.code !== "ESRCH") {
          console.error(`Failed to stop process group ${child.pid}:`, error.message);
          process.exitCode = 1;
        }
      }
    }
  }
  if (process.exitCode !== 1) process.exitCode = exitCode;
}

function start(name, command, args) {
  const child = spawn(command, args, {
    stdio: "inherit",
    detached: !windows,
  });
  children.add(child);
  child.on("error", (error) => {
    console.error(`Failed to start ${name}:`, error.message);
    children.delete(child);
    stop(1);
  });
  child.on("exit", (code, signal) => {
    children.delete(child);
    if (!stopping) {
      console.error(`${name} stopped (${signal ?? `exit ${code}`}); stopping the other server.`);
      stop(code || 1);
    }
  });
}

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

start("API", "uv", [
  "run", "--env-file", ".env", "uvicorn", "apps.api.main:app",
  "--reload", "--host", "0.0.0.0", "--port", "8000",
]);
if (!stopping) {
  if (windows) {
    start("Web", process.env.ComSpec || "cmd.exe", [
      "/d", "/s", "/c", "npm --prefix apps\\web run dev -- --hostname 0.0.0.0",
    ]);
  } else {
    start("Web", "npm", ["--prefix", "apps/web", "run", "dev", "--", "--hostname", "0.0.0.0"]);
  }
}
