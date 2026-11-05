# Guía de la Etapa 10: Emergencias (CU-05)

Cada paso trae **qué hace**, **qué debes ver** y **qué evidencia guardar**. Guarda las capturas
en una carpeta `evidencia_etapa10/` con el número de paso en el nombre (`E10-03_pruebas.png`).
Los comandos son para **PowerShell** en Windows, desde la carpeta del proyecto (donde está
`docker-compose.yml`). Antes de empezar, abre **Docker Desktop** y espera a que diga *Running*.

**Qué se construye:** Recepción registra una emergencia **sin cita** (R-06, NB-19), con la
mascota opcional (P3). Eso activa el protocolo, guarda el evento `EmergenciaIdentificada` y,
después de confirmar el registro, **notifica al veterinario**. Luego el personal clínico inicia
la atención (US20). Además existe la regla `TieneCitaConfirmada OR TieneEmergenciaActiva`, que
dice si una mascota puede recibir atención.

---

## Paso 0. Poner el código de la Etapa 10 en tu proyecto

> Si llegaste a copiar el zip anterior de **hospitalización** en tu proyecto, primero
> descarta esos cambios: `git restore .` y `git clean -fd src tests` (o vuelve a tu copia de
> la etapa 9). Hospitalización llegará como una etapa posterior.

```powershell
git checkout -b etapa-10
```

Descomprime `vetcare24_etapa10.zip` y **copia el contenido de su carpeta `vetcare24/` encima
de tu proyecto**: se reemplazan los archivos modificados y se agregan los nuevos. No borres tu `.env`.

```powershell
git status
git diff --stat
```

**Debes ver:** 10 archivos nuevos, entre ellos `domain/emergencia.py`,
`domain/reglas_emergencia.py`, `application/servicios_emergencias.py`,
`infrastructure/notificador.py` y las pruebas `test_emergencia.py`,
`test_servicios_emergencias.py` y `test_api_emergencias.py`.

**Evidencia E10-00:** captura de `git diff --stat`.

---

## Paso 1. Reconstruir las imágenes

```powershell
docker compose --profile tests build
```

- `--profile tests` incluye el servicio `tests`, que normalmente está apagado.
- `build` vuelve a crear las imágenes `app` y `tests`, ahora con el código nuevo.

**Debes ver:** termina sin errores.

---

## Paso 2. Lint

```powershell
docker compose --profile tests run --rm tests ruff check .
```

- `run --rm tests` crea un contenedor de pruebas, ejecuta el comando y lo borra al terminar.
- `ruff` revisa el estilo y los errores comunes de todo el código.

**Debes ver:** `All checks passed!`

> En la Etapa 9 este comando fallaba con 4 errores, así que el job `lint` del CI estaba en
> rojo. Ya está corregido (decisión N-13). Vale la pena mencionarlo en el reporte.

**Evidencia E10-02:** captura con `All checks passed!`.

---

## Paso 3. Pruebas y cobertura (SQLite + PostgreSQL)

```powershell
docker compose --profile tests run --rm tests pytest --cov-report=html:docs/evidencia/cobertura
```

- Ejecuta todas las pruebas. Las de persistencia corren dos veces: en SQLite y en PostgreSQL.
- `--cov-report=html:...` además deja un reporte de cobertura navegable en tu carpeta
  `docs/evidencia/cobertura/`.

**Debes ver al final:**
```
Required test coverage of 80% reached. Total coverage: 98.81%
574 passed
```
(La etapa 9 tenía 491: hay 83 pruebas nuevas.) Si aparece `skipped`, PostgreSQL no estaba
disponible: revisa `docker compose ps`.

Busca en la salida las dos pruebas que propone la matriz de tu informe (NB-19):
```powershell
docker compose --profile tests run --rm tests pytest -v -k "emergencia_sin_cita_se_registra or notifica_veterinario_tras_confirmar" --no-cov
```
**Debes ver:** 4 `PASSED` (cada prueba corre en sqlite y en postgres).

**Evidencia E10-03a:** captura de las últimas líneas (574 pruebas y la cobertura).
**Evidencia E10-03b:** captura de las 4 pruebas del informe en `PASSED`.
**Evidencia E10-03c:** abre `docs/evidencia/cobertura/index.html` y captura la tabla; los
archivos de emergencias deben estar al 100 %.

---

## Paso 4. Levantar la aplicación

```powershell
docker compose up --build -d
docker compose ps
```

- **No hace falta `down -v`**: al arrancar, la aplicación crea sola la tabla `emergencias` y
  conserva tus datos (N-10).
- `db` debe estar *healthy* y `app` *running*.

Si tu base está vacía, carga los CSV (si ya tiene datos, solo avisa y no hace nada):
```powershell
docker compose run --rm app python -m vetcare24.infrastructure.sembrado
```

**Evidencia E10-04:** captura de `docker compose ps`.

---

## Paso 5. Ver el contrato en Swagger

Abre **http://localhost:8000/docs**. Aparece una sección nueva **Emergencias**, y en
**Evaluaciones** una ruta más:

| Método | Ruta | Quién |
|---|---|---|
| POST | `/emergencias` | recepcion |
| POST | `/emergencias/{emergencia_id}/iniciar-atencion` | personal_clinico |
| GET | `/emergencias`, `/emergencias/{emergencia_id}` | todos los roles |
| GET | `/avisos-veterinario` | todos los roles |
| GET | `/mascotas/{mascota_id}/evaluaciones/atencion` | todos los roles |

**Evidencia E10-05:** captura de la sección Emergencias desplegada.

---

## Paso 6. Recorrido manual en Swagger

En cada ruta: **Try it out**, escribe el rol en `X-Rol`, llena los datos y **Execute**.
Captura la respuesta, que muestre el **código** y el **cuerpo**.

| # | Ruta y rol | Datos | Esperado |
|---|---|---|---|
| 6.1 | GET `/mascotas/VET-C002-MASCOTA/evaluaciones/atencion`, `veterinario` | — | **200**, `cumple: false`, motivos `SIN_CITA_CONFIRMADA`, `SIN_EMERGENCIA_ACTIVA` |
| 6.2 | POST `/emergencias`, `recepcion` | `{"motivo": "Atropellamiento", "mascota_id": "VET-C002-MASCOTA"}` | **201**, `estado: IDENTIFICADA`, `protocolo_activado: true`, `notificacion: notificado`. Anota el `emergencia_id`. |
| 6.3 | Repetir 6.1 | — | **200**, `cumple: true`: **sin cita, por ser emergencia** (R-06) |
| 6.4 | GET `/avisos-veterinario`, `veterinario` | — | **200**, el aviso de tu emergencia |
| 6.5 | POST `/emergencias`, `recepcion` | `{"motivo": "Intoxicación", "datos_paciente": "Gato atigrado, sin registro"}` | **201**, `mascota_id: null` (P3) |
| 6.6 | POST `/emergencias`, `veterinario` | `{"motivo": "x"}` | **403** `ACCESO_DENEGADO` (solo Recepción registra, A-01) |
| 6.7 | POST `/emergencias/{id de 6.2}/iniciar-atencion`, `personal_clinico` | — | **200**, `estado: EN_ATENCION`, con `atendida_en` |
| 6.8 | Repetir 6.7 | — | **409** `TRANSICION_INVALIDA`: "No se puede iniciar la atención de una emergencia que está en atención." |
| 6.9 | POST `/emergencias`, `recepcion` | `{"motivo": "   "}` | **422** `MOTIVO_VACIO` |
| 6.10 | GET `/eventos`, `veterinario` | — | **200**; al final, dos `EmergenciaIdentificada` con `agregado_tipo: Emergencia` |

**Evidencia E10-06.1 a E10-06.10:** una captura por fila. La pareja 6.1 y 6.3 demuestra la
regla OR, y 6.2 con 6.4 la notificación después del registro.

> En la terminal de PowerShell usa `curl.exe`, no `curl` (que es otro comando):
> ```powershell
> curl.exe -H "X-Rol: veterinario" http://localhost:8000/avisos-veterinario
> ```

---

## Paso 7. Evidencia automática (CSV y OpenAPI)

```powershell
docker compose --profile tests run --rm tests python -m tests.evidencia_emergencias
docker compose --profile tests run --rm tests python -m tests.evidencia_api
docker compose --profile tests run --rm tests python -m vetcare24.api.exportar_openapi docs/evidencia/openapi.json
```

- El primero ejecuta por HTTP los **20 escenarios de CU-05** (E01 a E20) contra la base de
  pruebas y escribe `docs/evidencia/api_emergencias.csv`. Si alguno no coincide, termina con error.
- El segundo regenera los 120 casos y las 20 transiciones (no deben cambiar).
- El tercero exporta el contrato actualizado.

**Debes ver:**
```
emergencias por la API: 20/20 escenarios coinciden
casos por la API:         120/120 coinciden
transiciones por la API:  20/20 coinciden
confirmación de las 60:   coincide
OpenAPI exportado: docs/evidencia/openapi.json (23 rutas)
```
(En la salida del primero también verás dos líneas `EMERGENCIA EMER-E01...`: es el aviso al
veterinario que escribe el notificador en el log.)

**Evidencia E10-07:** captura de las tres salidas. Abre `api_emergencias.csv` en Excel: la
columna `coincide` debe decir `True` en las 20 filas.

---

## Paso 8. Verificar en la base de datos

```powershell
docker compose exec db psql -U vetcare -d vetcare24 -c "SELECT emergencia_id, mascota_id, estado, identificada_en, atendida_en FROM emergencias;"
docker compose exec db psql -U vetcare -d vetcare24 -c "SELECT secuencia, evento, agregado_tipo, agregado_id FROM eventos_dominio WHERE agregado_tipo = 'Emergencia';"
docker compose exec db psql -U vetcare -d vetcare24 -c "\d emergencias"
```

- `exec db psql` abre el cliente de PostgreSQL dentro del contenedor de la base.

**Debes ver:** tus dos emergencias (una en `EN_ATENCION` y otra con `mascota_id` vacío), sus
dos eventos y, en `\d`, la llave foránea a `mascotas` **sin `NOT NULL`** (P3) y los `CHECK`.

**Evidencia E10-08:** captura de las tres consultas.

---

## Paso 9. CI/CD en GitHub Actions

```powershell
git add -A
git commit -m "Etapa 10: emergencias (CU-05) y CI en verde"
git push -u origin etapa-10
```

En GitHub abre un **Pull Request** de `etapa-10` hacia `main` y ve a **Actions**.
Los jobs son `lint` → `test` (con PostgreSQL) → `docker`.

**Debes ver:** los tres jobs en verde (en la etapa 9 `lint` estaba en rojo). En **Artifacts**
aparecen `cobertura` y el nuevo `evidencia`, con los CSV y el `openapi.json` generados por el CI.

**Evidencia E10-09a:** captura de la ejecución en verde.
**Evidencia E10-09b:** captura de Artifacts; descarga `evidencia` y guárdalo.

---

## Paso 10. Apagar

```powershell
docker compose down        # apaga y conserva los datos
```

---

## Para la matriz de trazabilidad

| Necesidad | Regla | Componente | Prueba |
|---|---|---|---|
| NB-19, R-06 | La emergencia se registra sin exigir cita | `ServicioDeEmergencias.atender_emergencia` · `Emergencia` · `RepositorioDeEmergencias` (sin citas) · `EmergenciaIdentificada` | `test_emergencia_sin_cita_se_registra`; E01, E02 |
| NB-19, CR-8 | Se notifica al veterinario después de confirmar el registro | `NotificadorDeVeterinario` · `BandejaDeAvisos` · Unidad de Trabajo | `test_notifica_veterinario_tras_confirmar`; `test_si_la_notificacion_falla_el_registro_se_conserva`; E10 |
| R-06, D-06 | `TieneCitaConfirmada OR TieneEmergenciaActiva` | `domain/reglas_emergencia.py` | `test_atencion_permitida`; E11, E12 |
| US20, A-01 | Recepción registra; el personal clínico inicia la atención | `control_de_acceso.py` · `CicloDeVidaDeEmergencia` | `test_cada_rol_solo_hace_lo_suyo`; E03, E04, E13, E14, E15 |
| P3 | Mascota opcional | `Emergencia.mascota_id`, llave foránea opcional | `test_emergencia_sin_mascota_registrada`; E02 |
| NB-20, D-13 | Contrato HTTP 200/201/400/401/403/404/409/422 | `api/rutas.py` · `api/errores_http.py` | `test_los_20_escenarios_del_recorrido_coinciden` |

## Qué validar con el profesor o el stakeholder

1. **CR-8 / N-07:** ¿quién identifica formalmente la emergencia? Se implementó Recepción (A-01).
2. **N-04:** ¿qué datos son obligatorios? Hoy solo el motivo.
3. **N-08:** ¿por qué canal se notifica al veterinario? Hoy: log y bandeja consultable.
4. **N-02 / N-06:** ¿cómo y cuándo se cierra una emergencia? ¿Se necesita un evento al iniciar la atención?
