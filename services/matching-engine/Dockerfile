FROM python:3.12-slim

WORKDIR /app

COPY services/common /app/common
COPY services/matching-engine/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/matching-engine /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8002

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
