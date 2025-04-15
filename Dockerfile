# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for some Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set timezone
RUN ln -fs /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime

# Create directories for output and batch files
RUN mkdir -p output batch_files

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the default command
CMD ["python", "main.py", "--crawl"]