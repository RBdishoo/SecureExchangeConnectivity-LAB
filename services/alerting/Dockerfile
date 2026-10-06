FROM python:3.12-slim

WORKDIR /app

COPY services/common /app/common
COPY detections /app/detections
COPY services/alerting/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/alerting /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8004
ENV PYTHONPATH=/app
ENV RULES_DIR=/app/detections
ENV ALERTS_DIR=/data/alerts
ENV LOGS_PATH=/data/logs/synthetic-events.jsonl

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
