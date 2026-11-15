FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CRAWLER_AUTH_MODE=public \
    CRAWLER_EMBEDDED_WORKER=true \
    CRAWLER_BROWSER_FALLBACK=true \
    CRAWLER_BROWSER_CHANNEL=chromium \
    CRAWLER_BROWSER_SANDBOX=false
WORKDIR /app
COPY requirements-lock.txt requirements-browser-lock.txt pyproject.toml ./
COPY src ./src
RUN apt-get update && apt-get install -y --no-install-recommends xvfb \
    && python -m pip install --no-cache-dir -r requirements-lock.txt -r requirements-browser-lock.txt \
    && python -m pip install --no-cache-dir --no-deps . \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /ms-playwright \
    && useradd --uid 10001 --create-home crawler \
    && mkdir -p /app/var && chown crawler:crawler /app/var
USER 10001:10001
EXPOSE 8000
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1366x768x24", "crawler", "serve", "--host", "0.0.0.0", "--port", "8000"]

