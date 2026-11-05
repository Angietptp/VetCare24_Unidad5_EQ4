# Bitácora E8 · GitHub Actions y protección de la rama `main`

## Laboratorio (repositorio CLN_U5_Laboratorio_EQ4, flujo «CI Business Logic»)

| # | Commit | Resultado | Qué pasó | Cómo se resolvió |
|---|---|---|---|---|
| 1 | Unidad 5: pruebas, TDD y CI | Roja (13 s) | `pytest` falló con `ModuleNotFoundError` al importar `src`: en el equipo local funcionaba, pero el flujo ejecuta pytest sin añadir la carpeta del proyecto al path. | Se agregó `pythonpath = ["."]` en `pyproject.toml`. |
| 2 | Corrige CI: pythonpath para que pytest encuentre src | Verde (11 s) | Todos los pasos pasaron: checkout, setup-python, instalación, Ruff, pytest con cobertura y compileall. | — |
| 3 | Rompe a propósito una prueba para ver el CI en rojo | Roja (14 s) | Se introdujo una aserción falsa intencional. Ruff pasó y falló solo el paso de pytest. | Fallo controlado: demuestra que el flujo detecta una regresión. |
| 4 | Revertir «Rompe a propósito…» | Verde (12 s) | Se revirtió con `git revert`, que conserva el historial. | — |

Capturas: `03_EVIDENCIAS/Laboratorio/E8_GitHub_Actions/`.

## VetCare 24 (repositorio VetCare24_Unidad5_EQ4)

- Flujo de tres trabajos encadenados: `lint` → `test` → `docker`.
- El trabajo `test` ejecuta pytest con PostgreSQL, genera la evidencia (120 casos, 20 transiciones, 20 escenarios de emergencias y OpenAPI) y publica dos artefactos: `cobertura.zip` y `evidencia.zip`.
- Primera ejecución del flujo de la etapa 10: verde en 2 min 24 s. Una segunda ejecución sobre el commit `bc6cdd3` terminó en verde en 1 min 53 s.
- Capturas: `03_EVIDENCIAS/PIA_VetCare24/E8_GitHub_Actions/01_Pipeline_CI/`.

## Autenticación al subir el código

GitHub ya no acepta contraseña en operaciones de Git. Los errores que aparecieron al subir VetCare 24 fueron:

1. «Password authentication is not supported for Git operations».
2. Push rechazado por falta del permiso `workflow` en el token.

Se resolvieron con un token personal con los permisos `repo` y `workflow`. El token no aparece en ninguna captura ni documento.
Capturas: `03_EVIDENCIAS/PIA_VetCare24/E8_GitHub_Actions/02_Subida_a_GitHub/`.

## Protección de la rama `main` (05/11/2026)

En VetCare24_Unidad5_EQ4 se creó el conjunto de reglas `main`:

- Estado: **Active**.
- Objetivo: la rama predeterminada.
- Reglas: se exige un pull request antes de fusionar y que pasen los 3 checks requeridos (`lint`, `test` y `docker`).

Para comprobarlo se intentó un push directo a `main`. GitHub lo rechazó (`GH013: Repository rule violations`) con los mensajes «Changes must be made through a pull request» y «3 of 3 required status checks are expected». El commit de prueba se descartó localmente con `git reset --hard HEAD~1`.
Capturas: `03_EVIDENCIAS/PIA_VetCare24/E8_GitHub_Actions/03_Proteccion_Rama_Main/`.

Nota: los flujos de GitHub Actions solo se ejecutan desde `.github/workflows/` en la raíz del repositorio. Este repositorio consolidado trae el flujo en la raíz, con los trabajos del laboratorio y de VetCare 24. Los nombres de los checks de esa regla corresponden al flujo anterior de VetCare 24; si se quieren exigir los de este flujo, hay que actualizarlos en la regla.
