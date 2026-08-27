FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY app ./app

CMD ["sh", "-c", "exec uvicorn app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080}"]
