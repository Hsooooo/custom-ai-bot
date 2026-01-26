FROM python:3.10-slim
WORKDIR /app

COPY workers/worker-brief/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY workers/shared /app/shared

COPY workers/worker-brief/main.py .
COPY workers/worker-brief/external_services.py .

CMD ["python", "main.py"]
