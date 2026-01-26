FROM python:3.10-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY ../shared /app/shared

COPY main.py .
COPY external_services.py .

CMD ["python", "main.py"]
