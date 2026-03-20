unzip ashbal_os_FINAL.zip
cd ashbal_os_FINAL
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port $PORT
