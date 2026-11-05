# Laboratorio U5 · Pedidos (proyecto base)

Proyecto de pedidos con las pruebas de la Unidad 5: dominio, TDD, repositorio con SQLAlchemy, servicio con mock, seguridad, cobertura y Ruff.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
python -m ruff check src tests
```

| Archivo de pruebas | Qué verifica |
|---|---|
| `tests/test_order.py` | Descuento VIP, cliente regular, deuda y total inválido |
| `tests/test_tdd_confirmar_dos_veces.py` | Ciclo TDD: no confirmar dos veces |
| `tests/test_order_csv.py` | Casos CP01 a CP12 leídos de `datos/` |
| `tests/test_repository.py` | Commit y rollback con SQLite en memoria |
| `tests/test_service.py` | Pasarela de pago simulada con mock |
| `tests/test_security.py` | Reglas de cancelación |

Las 20 pruebas del laboratorio guiado dieron 100 % de cobertura (Reporte_Cobertura/Laboratorio). La prueba parametrizada de los CSV agrega 12 casos más: el conjunto completo corre 32 pruebas con 100 % de cobertura.
Los CSV de `datos/` son ficticios y no se cargan solos: se leen con `csv.DictReader`.
