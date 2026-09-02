FROM python:3.11-slim

WORKDIR /app

COPY services/gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core
COPY services/__init__.py ./services/__init__.py
COPY services/gateway ./services/gateway

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "services.gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
