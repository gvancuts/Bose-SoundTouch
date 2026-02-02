FROM python:3.12-alpine

WORKDIR /app

COPY proxy_server.py soundtouch-controller-proxy.html favicon.ico ./

ENV SOUNDTOUCH_PORT=8000
ENV SOUNDTOUCH_DEVICE_IP=""

EXPOSE ${SOUNDTOUCH_PORT}

CMD ["python3", "proxy_server.py"]
