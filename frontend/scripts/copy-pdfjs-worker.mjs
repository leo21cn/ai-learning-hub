// 构建后把 PDF.js worker 从 node_modules 复制到 dist 根目录,
//让生产环境通过 `/pdf.worker.min.mjs` 可直接拉取(nginx 默认静态目录即可服务)。
//该步骤独立于 `vite build`,确保 worker 一定被打入产物。
import { copyFile, access, constants } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const SRC = resolve(
  ROOT,
  "node_modules/pdfjs-dist/build/pdf.worker.min.mjs",
);
const DEST = resolve(ROOT, "dist/pdf.worker.min.mjs");

try {
  await access(SRC, constants.F_OK);
} catch {
  console.error(
    `[copy-pdfjs-worker] 源文件不存在: ${SRC}\n` +
      "请确认已执行 `npm install`,且 pdfjs-dist ^4.7.76 已安装。",
  );
  process.exit(1);
}

await copyFile(SRC, DEST);
console.log(
  `[copy-pdfjs-worker] 已复制 PDF.js worker: ${SRC} -> ${DEST}`,
);