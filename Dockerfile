FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY api.py compiler.py schema.py tools.py ./
COPY form.html ./
COPY static/ ./static/

# Install dependencies using UV
RUN uv pip install --system -e .

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8000

# Run with UV
CMD ["uv", "run", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
