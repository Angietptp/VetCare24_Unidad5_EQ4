"""Exporta el contrato OpenAPI a un archivo JSON (evidencia del PIA).

Uso:  python -m vetcare24.api.exportar_openapi [ruta]      (por omisión, openapi.json)
No necesita base de datos: el contrato se genera de las rutas.
"""

import json
import sys
from pathlib import Path

from vetcare24.api.main import create_app


def main(argv: list[str]) -> None:
    ruta = Path(argv[0]) if argv else Path("openapi.json")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    contrato = create_app().openapi()
    ruta.write_text(json.dumps(contrato, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI exportado: {ruta} ({len(contrato['paths'])} rutas)")


if __name__ == "__main__":
    main(sys.argv[1:])
