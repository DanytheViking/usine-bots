FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sentinelle ./sentinelle
COPY tests ./tests
RUN mkdir -p /app/data && useradd -r -u 10001 sentinelle && chown sentinelle /app/data
USER sentinelle
ENV DATA_DIR=/app/data PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "-m", "sentinelle.main"]
