FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY moon ./moon
COPY tests ./tests
RUN mkdir -p /app/data && useradd -r -u 10001 moon && chown moon /app/data
USER moon
ENV DATA_DIR=/app/data PYTHONUNBUFFERED=1
CMD ["python3", "-m", "moon.bot"]
