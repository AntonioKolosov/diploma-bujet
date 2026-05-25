FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Render dynamically sets the PORT environment variable
ENV PORT=8501
EXPOSE $PORT

# Healthcheck to verify the app is running
HEALTHCHECK CMD curl --fail http://localhost:${PORT}/_stcore/health || exit 1

# Start the application using the start script
CMD ["./start.sh"]
