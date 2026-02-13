FROM python:3.12-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ src/

# Install package
RUN pip install --no-cache-dir .

# Logs directory
RUN mkdir -p logs

EXPOSE 8000 8001

# Default: run API server
CMD ["uvicorn", "a10_guardian.main:app", "--host", "0.0.0.0", "--port", "8000"]
