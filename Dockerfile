# Friction Finder: one image, one process. Builds the React app, generates the synthetic data,
# then serves everything from FastAPI. Works on Render (free tier) and Hugging Face Spaces.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements-deploy.txt ./
RUN pip install -r requirements-deploy.txt
COPY . .
COPY --from=web /web/dist ./web/dist
RUN python data/generate.py \
 && useradd -m app && chown -R app /app
USER app
# Render and Hugging Face set PORT; 8000 locally.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
