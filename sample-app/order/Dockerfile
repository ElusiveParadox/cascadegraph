FROM python:3.13.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir requests==2.34.2 urllib3==2.8.0
COPY client.py custom_retry.py server.py ./
COPY --from=instrumentation telemetry.py ./
USER 65532:65532
EXPOSE 8000
CMD ["python", "server.py"]
