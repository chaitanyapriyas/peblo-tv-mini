FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY data data
COPY assets assets

EXPOSE 8000

CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && python -m backend.seed_shows && uvicorn backend.app:app --host 0.0.0.0 --port 8000"]
