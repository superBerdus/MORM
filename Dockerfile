FROM python:3.11-slim

# OpenCV and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY core/ ./core/
COPY app/ ./app/
COPY static/ ./static/

# Create runtime data directories
RUN mkdir -p /workspace/data/uploads /workspace/data/outputs

EXPOSE 8085

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]
