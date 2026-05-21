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

# Porta default 7860 (HF Spaces espera nesse valor). Outras plataformas
# (Fly, Koyeb, Render) injetam $PORT que sobrescreve.
# Local: rodar com `docker run -p 8080:7860 ...` ou `-e PORT=8080`.
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
