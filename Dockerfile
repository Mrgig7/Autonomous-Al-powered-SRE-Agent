# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Export requirements (without dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

# Runtime stage
FROM python:3.11-slim as runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r sre_agent && useradd -r -g sre_agent sre_agent

# Install dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Set PYTHONPATH
ENV PYTHONPATH=/app/src

# Change ownership to non-root user
RUN chown -R sre_agent:sre_agent /app

USER sre_agent

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "sre_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
