# Multi-stage Dockerfile for FastAPI backend
FROM docker.m.daocloud.io/library/python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 可选构建参数:代理(用于访问 Debian 镜像 / PyPI);留空则直连。
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY}

# 使用清华 Debian 镜像 (trixie) ,避免 docker.io 网络不稳。
# python:3.11-slim 实际为 Debian 13 (trixie) ,配置在 /etc/apt/sources.list.d/debian.sources (deb822 格式)。
RUN cat > /etc/apt/sources.list.d/debian.sources <<'EOF'
Types: deb
URIs: http://mirrors.tuna.tsinghua.edu.cn/debian
Suites: trixie trixie-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp

Types: deb
URIs: http://mirrors.tuna.tsinghua.edu.cn/debian-security
Suites: trixie-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.pgp
EOF

# Install system deps for psycopg2 + uvicorn[standard] + LibreOffice (PPT→PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    libreoffice-core libreoffice-impress libreoffice-common \
    poppler-utils \
    fonts-dejavu fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (use pip instead of poetry to avoid lock-file dance)
# 优先用清华 PyPI 镜像加速国内网络;失败再回落到官方源。
COPY pyproject.toml ./
RUN mkdir -p /root/.pip && \
    printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\ntimeout = 60\n' > /root/.pip/pip.conf && \
    pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install \
      "fastapi==0.115.5" \
      "uvicorn[standard]==0.32.1" \
      "sqlalchemy[asyncio]==2.0.36" \
      "alembic==1.14.0" \
      "psycopg2-binary==2.9.10" \
      "asyncpg==0.30.0" \
      "pydantic==2.10.3" \
      "pydantic-settings==2.6.1" \
      "python-jose[cryptography]==3.3.0" \
      "passlib[bcrypt]==1.7.4" \
      "python-multipart==0.0.20" \
      "slowapi==0.1.9" \
      "redis==5.2.0" \
      "httpx==0.28.1" \
      "PyJWT==2.10.1" \
      "dashscope>=1.20.0"

# Copy app source
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Storage dir for materials
RUN mkdir -p /app/storage/documents /app/storage/logs
VOLUME ["/app/storage"]

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/public/health || exit 1

CMD ["./entrypoint.sh"]
