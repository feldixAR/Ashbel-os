FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y unzip && rm -rf /var/lib/apt/lists/*

COPY ashbal_os_FINAL-1.zip .

RUN unzip ashbal_os_FINAL-1.zip && rm ashbal_os_FINAL-1.zip

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
