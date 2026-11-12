FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY recolteur ./recolteur
COPY tests ./tests
COPY docs ./docs
RUN mkdir -p /app/data && useradd -r -u 10001 recolteur && chown recolteur /app/data
USER recolteur
ENV DATA_DIR=/app/data PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python3", "-m", "recolteur.main"]
