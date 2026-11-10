FROM python:3.12-slim
WORKDIR /srv/api
RUN apt-get update && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu fonts-indic \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
COPY scripts ./scripts
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["sh", "/srv/api/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
