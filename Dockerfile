FROM python:3.12-slim
WORKDIR /app
COPY demo.py .
CMD ["python", "demo.py"]
