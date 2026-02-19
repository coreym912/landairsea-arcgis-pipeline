FROM python:3.9-slim

WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Configure Gunicorn for better memory management
CMD exec gunicorn --bind :$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 0 \
    --worker-tmp-dir /dev/shm \
    --worker-class gthread \
    main:app
