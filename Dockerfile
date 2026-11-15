FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-lock.txt pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements-lock.txt \
    && python -m pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home crawler \
    && mkdir -p /app/var && chown crawler:crawler /app/var
USER 10001:10001
EXPOSE 8000
CMD ["crawler", "serve", "--host", "0.0.0.0", "--port", "8000"]

