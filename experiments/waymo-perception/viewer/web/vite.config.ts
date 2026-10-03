import { defineConfig, type Plugin } from "vite";
import fs from "node:fs";
import path from "node:path";

const MIME: Record<string, string> = {
  ".json": "application/json",
  ".wpc": "application/octet-stream",
  ".jpg": "image/jpeg",
  ".png": "image/png",
};

/** Serve exported scene bundles from the cache root at /bundles/* with Range support. */
function bundleServer(): Plugin {
  const root = process.env.WAYMO_VIEWER_BUNDLES ?? path.join(process.env.HOME ?? "", ".cache/waystone/waymo-perception/viewer/bundles");
  return {
    name: "waymo-bundle-server",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        if (!url.startsWith("/bundles/")) return next();
        const rel = decodeURIComponent(url.slice("/bundles/".length));
        if (rel === "" || rel === "index.json") {
          const scenes: { slice: string; context: string; url: string }[] = [];
          if (fs.existsSync(root)) {
            for (const slice of fs.readdirSync(root)) {
              const sdir = path.join(root, slice);
              if (!fs.statSync(sdir).isDirectory()) continue;
              for (const ctx of fs.readdirSync(sdir)) {
                if (fs.existsSync(path.join(sdir, ctx, "scene.json"))) scenes.push({ slice, context: ctx, url: `/bundles/${slice}/${ctx}/` });
              }
            }
          }
          res.setHeader("Content-Type", "application/json");
          res.setHeader("Access-Control-Allow-Origin", "*");
          res.end(JSON.stringify({ root, scenes }));
          return;
        }
        const file = path.resolve(root, rel);
        if (!file.startsWith(path.resolve(root) + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
          res.statusCode = 404;
          res.end("not found");
          return;
        }
        const size = fs.statSync(file).size;
        res.setHeader("Content-Type", MIME[path.extname(file)] ?? "application/octet-stream");
        res.setHeader("Accept-Ranges", "bytes");
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.setHeader("Cache-Control", "no-cache");
        const range = req.headers.range;
        if (range) {
          const m = /bytes=(\d*)-(\d*)/.exec(range);
          const start = m && m[1] ? Number(m[1]) : 0;
          const end = m && m[2] ? Number(m[2]) : size - 1;
          res.statusCode = 206;
          res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
          res.setHeader("Content-Length", String(end - start + 1));
          fs.createReadStream(file, { start, end }).pipe(res);
        } else {
          res.setHeader("Content-Length", String(size));
          fs.createReadStream(file).pipe(res);
        }
      });
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [bundleServer()],
  server: { host: "127.0.0.1", port: 5173, strictPort: false },
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
  worker: { format: "es" },
});
