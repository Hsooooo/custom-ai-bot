FROM python:3.10-slim

WORKDIR /app

COPY workers/worker-coach/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY workers/worker-coach/main.py main.py
COPY workers/worker-coach/prompts /app/prompts

CMD ["python", "-u", "main.py"]
