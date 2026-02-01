FROM python:3.10-slim

WORKDIR /app

COPY tools/readonly-dashboard/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY tools/readonly-dashboard/app.py app.py

EXPOSE 8090

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
