# Build stage
FROM node:18 AS build

WORKDIR /app

# Copy package files
COPY src/frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source
COPY src/frontend/ .

# Build the app
RUN npm run build

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python requirements and install
COPY src/frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built assets from build stage
COPY --from=build /app/dist ./dist
COPY src/frontend/frontend_server.py .

EXPOSE 3000

CMD ["uvicorn", "frontend_server:app", "--host", "0.0.0.0", "--port", "3000"]

# OTHER DOCKERFILE
FROM mcr.microsoft.com/devcontainers/python:3.11-bullseye AS base
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.6.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY uv.lock pyproject.toml /app/

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Backend app setup
COPY . /app  
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM base

COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3000
CMD ["uv","run","uvicorn", "frontend_server:app", "--host", "0.0.0.0", "--port", "3000"]