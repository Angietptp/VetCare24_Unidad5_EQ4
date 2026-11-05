# VetCare 24 — PIA Componentes de Lógica de Negocio (Equipo 4)

Estado: **Etapa 10 — Emergencias (CU-05)**: registro sin cita, protocolo, notificación al veterinario y atención del personal clínico, por dominio, base de datos y API. Ver `docs/decisiones.md` (sección N) y la guía `docs/guia_etapa10.md`.

## Estructura
```
src/vetcare24/
  domain/          reglas de negocio puras (sin FastAPI ni SQLAlchemy)
  application/     casos de uso, comandos, consultas, control de acceso
  infrastructure/  configuración, persistencia, importador de CSV
  api/             FastAPI + OpenAPI
tests/             pruebas
data/alumno/       CSV del alumno (solo lectura)
docs/              decisiones y, más adelante, matriz de trazabilidad
docker/initdb/     crea la base vetcare24_test
```

## Ejecutar con Docker
```bash
cp .env.example .env
docker compose up --build            # API en http://localhost:8000/docs
docker compose --profile tests run --rm tests   # pruebas + cobertura
```

## Ejecutar sin Docker
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Oráculo (Etapa 2)
Genera los resultados esperados de los 120 casos y las 20 transiciones en `docs/evidencia/`:
```bash
docker compose --profile tests run --rm tests python -m tests.oraculo
```
Sin Docker (PowerShell): `$env:PYTHONPATH="src"; python -m tests.oraculo`

## Evidencia de eventos (Etapa 6)
```bash
docker compose --profile tests run --rm tests python -m tests.evidencia_eventos
```
Sin Docker (PowerShell): `$env:PYTHONPATH="src"; python -m tests.evidencia_eventos`

## Base de datos (Etapa 7)
Cargar los CSV en la base de datos de la aplicación (crea el esquema si falta):
```bash
docker compose up -d db
docker compose run --rm app python -m vetcare24.infrastructure.sembrado
```
Las pruebas de persistencia corren en SQLite y, dentro de Docker Compose, también en PostgreSQL.

## API REST (Etapa 7)
Con `docker compose up --build` la documentación interactiva queda en http://localhost:8000/docs.
Cada solicitud indica el rol en el encabezado `X-Rol` (`recepcion`, `veterinario`, `personal_clinico`, `responsable`).
```bash
docker compose run --rm app python -m vetcare24.infrastructure.sembrado   # datos del paquete
curl -H "X-Rol: recepcion" http://localhost:8000/servicios
curl -H "X-Rol: recepcion" "http://localhost:8000/citas?estado=SOLICITADA"
curl -X POST -H "X-Rol: recepcion" http://localhost:8000/citas/CITA-XXXX/confirmar
```
Códigos de error: 400 solicitud mal formada, 401 falta rol, 403 sin permiso, 404 no existe, 409 transición inválida o capacidad insuficiente, 422 regla de negocio no cumplida (ver K en `docs/decisiones.md`).


## Evidencia de la API (Etapa 8)
```bash
docker compose --profile tests run --rm tests python -m tests.evidencia_api
docker compose --profile tests run --rm tests python -m vetcare24.api.exportar_openapi docs/evidencia/openapi.json
```
Genera `docs/evidencia/api_casos.csv`, `api_transiciones.csv` y `openapi.json`.
Las evaluaciones por HTTP: `GET /citas/{id}/evaluaciones/procesamiento` y `/beneficio`.

## Vacunación (Etapa 9)
Si tu base de desarrollo es de la versión anterior, reiníciala (la tabla de eventos cambió):
```bash
docker compose down -v
docker compose up -d db
docker compose run --rm app python -m vetcare24.infrastructure.sembrado
```
Endpoints: `POST/GET /mascotas/{id}/vacunaciones`, `GET /mascotas/{id}/vacunaciones/seguimiento`,
`GET /vacunas/proximas`, `GET /esquemas-vacunacion`.

## Emergencias (Etapa 10)
No hace falta reiniciar la base: al arrancar, la aplicación crea la tabla `emergencias` que falte.
Endpoints: `POST /emergencias` (Recepción), `POST /emergencias/{id}/iniciar-atencion` (personal clínico),
`GET /emergencias`, `GET /emergencias/{id}`, `GET /mascotas/{id}/evaluaciones/atencion`, `GET /avisos-veterinario`.
Evidencia (20 escenarios por HTTP):
```bash
docker compose --profile tests run --rm tests python -m tests.evidencia_emergencias
```
Sin Docker (PowerShell): `$env:PYTHONPATH="src"; python -m tests.evidencia_emergencias`

