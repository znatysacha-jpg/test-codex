FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway ./gateway
COPY scripts ./scripts
COPY agents ./agents
COPY deployments ./deployments
COPY memory_stores ./memory_stores
COPY memory_seed ./memory_seed
# Base SQLite : montez un volume persistant sur /data (sinon l'historique des validations est perdu au redémarrage)
ENV DB_PATH=/data/instinct.db
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn gateway.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
