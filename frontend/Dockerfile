# Multi-stage Dockerfile for Vite + React
FROM docker.m.daocloud.io/library/node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# npm ci 需要 lock 文件;若没有则用 npm install
RUN npm install --no-audit --no-fund --prefer-offline
COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js index.html ./
COPY scripts ./scripts
COPY src ./src
RUN npm run build && \
    # 将 PDF.js worker 复制到 dist 根目录供运行时加载
    cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs dist/pdf.worker.min.mjs

# Runtime:静态资源由 nginx 提供
FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
