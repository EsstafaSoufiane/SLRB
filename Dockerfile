FROM python:3.9-slim

# Install system dependencies including ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
