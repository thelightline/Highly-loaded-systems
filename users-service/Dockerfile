FROM python:3.11-slim
WORKDIR /app
COPY users-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common /app/common
COPY users-service/ /app/
ENV PYTHONPATH=/app
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8001"]
