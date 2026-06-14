# --- Stage 1: build the React frontend ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build      # outputs /fe/dist

# --- Stage 2: python backend (uv) serving API + the built frontend ---
FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend

# Install deps first (better layer caching)
COPY backend/pyproject.toml ./
RUN uv sync || true
COPY backend/ ./

# Drop the built frontend where main.py serves it (backend/app/static)
COPY --from=frontend /fe/dist ./app/static

ENV PORT=8000
EXPOSE 8000
# Shell form so $PORT (set by Render/Railway/Fly) is expanded.
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
