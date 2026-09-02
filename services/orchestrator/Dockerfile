FROM python:3.11-slim

WORKDIR /app

COPY services/orchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core
COPY services/__init__.py ./services/__init__.py
COPY services/orchestrator ./services/orchestrator

ENV PYTHONPATH=/app
EXPOSE 8001

CMD ["uvicorn", "services.orchestrator.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
