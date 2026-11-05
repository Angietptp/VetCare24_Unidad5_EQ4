# Etapa "runtime": solo lo necesario para ejecutar la API.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src ./src
COPY data ./data
ENV DATA_DIR=/app/data/alumno
EXPOSE 8000
CMD ["uvicorn", "vetcare24.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Etapa "dev": agrega herramientas de prueba, pruebas y datos. La usa el servicio "tests".
FROM runtime AS dev
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY pyproject.toml ./
COPY tests ./tests
CMD ["pytest"]
