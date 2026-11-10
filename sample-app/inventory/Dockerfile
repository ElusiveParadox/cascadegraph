FROM python:3.13.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server.py ./
COPY --from=instrumentation telemetry.py ./
USER 65532:65532
EXPOSE 8000
CMD ["python", "server.py"]
