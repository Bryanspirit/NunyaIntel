# NunyaIntel in a container. The image holds code only: the licensed GRID data and the extract
# built from it are mounted at run time (see compose.yaml), so the image can't leak them.

# ---- 1. build the React app ------------------------------------------------------------------
FROM node:24.15.0-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 2. the Python app that serves it ---------------------------------------------------------
FROM python:3.14.5-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STL_DATA_DIR=/data/grid
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# editable install: the package finds web/dist and data/cache relative to /app
RUN pip install --no-cache-dir -e .
COPY --from=web /web/dist ./web/dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# strip Windows line endings, just in case the file was checked out with CRLF
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
 && useradd --create-home --uid 1000 app \
 && mkdir -p data/cache \
 && chown -R app:app /app/data
USER app
EXPOSE 4811
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4811/api/meta', timeout=4)"
# 0.0.0.0 inside the container; compose publishes it on the host's 127.0.0.1 only
ENTRYPOINT ["sh", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["nunyaintel", "serve", "--host", "0.0.0.0", "--port", "4811"]
