# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set timezone to KST (Asia/Seoul)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set working directory
WORKDIR /app

# Install system dependencies (if any needed for pandas/numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create volume mount point for persistent data (token, history, logs)
VOLUME ["/app"]

# Run the application
CMD ["python", "main_auto_trade.py"]
