FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY main.py .

# Create data directory for persistence
RUN mkdir -p /app/data

# Set Python path
ENV PYTHONPATH=/app

# Run the bot
CMD ["python", "main.py"]
