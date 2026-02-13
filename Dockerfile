FROM python:3.9-slim

WORKDIR /app

# Install common build dependencies (helps wheel compilation)
RUN apt-get update && \
	apt-get install -y --no-install-recommends \
		build-essential \
		gcc \
		libssl-dev \
		libffi-dev \
		ca-certificates && \
	rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel && \
	pip install --no-cache-dir -r requirements.txt

# Copy the script
# Copy the script
COPY daily_airline-digest_email_sender.py .

# Set the entrypoint to run the script
ENTRYPOINT ["python", "/app/daily_airline-digest_email_sender.py"]