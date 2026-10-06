FROM python:3.12-slim

WORKDIR /app

COPY services/common /app/common
COPY services/market-data/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/market-data /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8003

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
