FROM python:3.13-alpine
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY syncover.py /app/syncover.py
ENTRYPOINT ["python", "/app/syncover.py", "--config", "/config/config.json"]
