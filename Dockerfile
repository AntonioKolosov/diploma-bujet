FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Make start script executable and fix Windows line endings (CRLF to LF)
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Render dynamically sets the PORT environment variable
ENV PORT=8501
EXPOSE $PORT

# Start the application using the start script
CMD ["./start.sh"]
