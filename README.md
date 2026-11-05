# Unidad 5 · Integración, Pruebas y Calidad

**Curso:** Componentes de Lógica de Negocios · **Profesor:** Miguel Ángel Gómez Marroquín · **Fecha:** 05/11/2026

**Equipo 4:** García Cerda Randal Guillermo (2112493) · Sarmiento Hernández Cesar Martín (2119427) · Torres Pasillas Angela Susana (2101844)

Este repositorio reúne la entrega final de la Unidad 5: el laboratorio guiado, el proyecto VetCare 24, las evidencias, el reporte de cobertura y la documentación.

## Estructura

```
Unidad5-Integracion-Pruebas-Calidad-Equipo4/
├── README.md
├── .gitignore
├── .github/workflows/ci.yml
├── ejecutar_todas_las_pruebas.ps1
├── 01_LABORATORIO_U5/
│   ├── laboratorio_U5/        proyecto final (src, tests, pyproject, requirements)
│   ├── TDD_RED_BASELINE/      copia en fase RED del ciclo TDD
│   ├── datos/                 casos_de_prueba.csv, clientes_prueba.csv, pedidos_prueba.csv
│   └── recursos/              instrucciones, proyecto base original, base SQLite de demostración
├── 02_PIA_VETCARE24/          código, pruebas, Docker Compose y evidencia generada
├── 03_EVIDENCIAS/
│   ├── Laboratorio/           E1 a E8
│   └── PIA_VetCare24/         etapas 1 a 10, E8 (CI, GitHub, protección de rama) y E9
├── docs/
│   ├── Reporte_Unidad_5.docx / .pdf
│   ├── Laboratorio_Guiado_Unidad_5_Completado.docx
│   ├── Bitacora/
│   └── Matrices/
└── Reporte_Cobertura/
    ├── Laboratorio/           reporte HTML (abrir index.html)
    └── VetCare24/             html/ (abrir index.html), coverage.xml y capturas
```

## Resultados

| Proyecto | Pruebas | Cobertura | Verificaciones |
|---|---|---|---|
| Laboratorio (guiado) | 20 | 100 % | Ruff, compileall y GitHub Actions |
| Laboratorio (conjunto completo, con la prueba de los CSV) | 32 | 100 % | Ruff y pytest (Figura 88) |
| VetCare 24 | 584 | 99 % (98.81 % con ramas) | Ruff, pytest con PostgreSQL, 120 casos, 20 transiciones, 20 escenarios y Docker |

Nota: las 20 pruebas del laboratorio guiado dieron 100 % (`Reporte_Cobertura/Laboratorio`). Después se agregó `tests/test_order_csv.py` (12 casos tomados de `datos/`): el conjunto completo corre 32 pruebas con 100 % de cobertura (53 declaraciones), como muestra la Figura 88 de `03_EVIDENCIAS/Laboratorio/E7_Cobertura_y_Calidad`.

## Cómo ejecutar

### Todo de una vez

```powershell
powershell -ExecutionPolicy Bypass -File .\ejecutar_todas_las_pruebas.ps1
```

Corre el laboratorio (Ruff, pytest y cobertura) y VetCare 24 en Docker (requiere Docker Desktop abierto). Con `-SoloLaboratorio` o `-SoloVetCare` se corre solo una parte.

### Laboratorio

```powershell
cd 01_LABORATORIO_U5\laboratorio_U5
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -v --cov=src --cov-report=html --cov-fail-under=80
python -m ruff check src tests
```

### VetCare 24

```powershell
cd 02_PIA_VETCARE24
copy .env.example .env
docker compose --profile tests build tests
docker compose --profile tests run --rm tests
docker compose up --build        # API en http://localhost:8000/docs
```

## Integración continua y protección de rama

`.github/workflows/ci.yml` ejecuta el laboratorio (Python 3.11) y VetCare 24 (lint, pruebas con PostgreSQL y Docker). Los flujos solo corren desde la raíz del repositorio, por eso están aquí y no dentro de cada proyecto.
La rama `main` de VetCare 24 se protegió con un conjunto de reglas (pull request y checks obligatorios); el detalle y las capturas están en `docs/Bitacora/Bitacora_E8_GitHub_Actions.md`.

## Notas

- No se incluyen entornos virtuales, archivos `.env`, tokens ni credenciales.
- Los datos de los CSV son ficticios.
- Los documentos de las unidades 2 y 3 (BRD, ADR, diagramas) no están en este repositorio.
