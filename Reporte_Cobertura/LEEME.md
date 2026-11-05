# Reporte de cobertura

| Proyecto | Resultado | Contenido |
|---|---|---|
| Laboratorio | 20 pruebas, 100 % (53 declaraciones, 0 sin cubrir) | `Laboratorio/index.html` (reporte HTML de coverage.py 7.17.2, 05/11/2026) |
| VetCare 24 | 584 pruebas, 99 % (98.81 % con ramas) | `VetCare24/html/index.html` (reporte HTML de coverage.py 7.17.2, 05/11/2026), `VetCare24/coverage.xml` (artefacto de GitHub Actions) y capturas |

Para abrir el reporte del laboratorio, abre `Laboratorio/index.html` en el navegador.
Para abrir el de VetCare 24, abre `VetCare24/html/index.html`. Se genera con:

```powershell
docker compose --profile tests run --rm tests pytest --cov-report=html:docs/evidencia/cobertura
```
