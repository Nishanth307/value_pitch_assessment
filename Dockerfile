# --- Stage 1: Build Dependencies ---
FROM python:3.11-alpine AS builder

WORKDIR /build

# Install compilation tools for potential C extensions in requirements
RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Runtime Environment ---
FROM python:3.11-alpine

WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /root/.local /root/.local
COPY . /app

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app:create_app
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 5000

# Run the seeding script on startup before starting Flask
CMD ["sh", "-c", "python3 scripts/seed.py && flask run"]
