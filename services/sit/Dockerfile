FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/sit/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared && rm -rf /tmp/shared
COPY services/sit/sit ./sit
EXPOSE 8000
CMD ["uvicorn", "sit.main:app", "--host", "0.0.0.0", "--port", "8000"]
