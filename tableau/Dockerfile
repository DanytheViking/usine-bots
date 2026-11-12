FROM python:3.12-slim
RUN pip install --no-cache-dir requests==2.32.3 && useradd -r -u 10002 tableau
WORKDIR /app
COPY tableau ./tableau
COPY tests ./tests
COPY docker-compose.yml ./
USER tableau
ENV PYTHONUNBUFFERED=1
CMD ["python3", "-m", "tableau.server"]
