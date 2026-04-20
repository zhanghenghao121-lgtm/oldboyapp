FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=180
ENV PIP_RETRIES=10
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com

RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing -o Acquire::Retries=5 \
    build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . ./

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && python manage.py init_admin && gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout ${GUNICORN_TIMEOUT:-1800} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-60} --keep-alive ${GUNICORN_KEEP_ALIVE:-5}"]
