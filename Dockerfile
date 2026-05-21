# Multi-stage build
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install -e ".[dev]" || \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/install/bin:$PATH \
    PYTHONPATH=/install/lib/python3.11/site-packages
COPY --from=builder /install /install
COPY src /app/src
USER 1000

# Porta configurável via variável PORT (Hugging Face Spaces injeta 7860,
# Fly/Koyeb/Render injetam $PORT). Default 8080 quando rodando local.
ENV PORT=8080
EXPOSE 8080 7860
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
