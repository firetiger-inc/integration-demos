FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ddtrace_app.py .

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

# Run the application
CMD ["python", "ddtrace_app.py"]