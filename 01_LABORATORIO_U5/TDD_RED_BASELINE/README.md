# TDD_RED_BASELINE

Copia del proyecto en el estado **antes** de la guarda `already confirmed` (paso E3, fase RED).

- `src/domain.py` no valida que el pedido ya esté confirmado.
- `tests/test_tdd_confirmar_dos_veces.py` sí contiene la prueba nueva, por lo que **falla a propósito**.

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -v
```

Resultado esperado: `1 failed` (`DID NOT RAISE ValueError`) y el resto en verde. La versión corregida (GREEN) está en `../laboratorio_U5`.
Esta carpeta no se ejecuta en el flujo de integración continua.
