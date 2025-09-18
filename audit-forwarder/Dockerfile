FROM python:3.12-slim
WORKDIR /app
RUN pip install psycopg[binary]
COPY main.py .
CMD ["python","/app/main.py"]
