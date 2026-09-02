FROM python:3.11-slim

WORKDIR /app

COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core
COPY services/__init__.py ./services/__init__.py
COPY services/worker ./services/worker

ENV PYTHONPATH=/app
EXPOSE 8002

CMD ["uvicorn", "services.worker.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
