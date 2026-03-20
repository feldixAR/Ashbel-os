FROM python:3.11

WORKDIR /app

COPY ashbal_os_FINAL-1.zip .

RUN python -m zipfile -e ashbal_os_FINAL-1.zip .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
