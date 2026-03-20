FROM python:3.11

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y unzip
RUN unzip ashbal_os_FINAL.zip

WORKDIR /app/ashbal_os_FINAL

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
