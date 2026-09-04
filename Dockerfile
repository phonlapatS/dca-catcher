# Stage 1: Install dependencies
FROM python:3.10-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only necessary source code
COPY src/ ./src/
COPY requirements.txt .

# Don't run as root
RUN useradd -m appuser
USER appuser

CMD ["python", "-m", "src.bot"]
