# Registro de decisiones — PIA VetCare 24 (Equipo 4)

**Principio rector.** El dominio se deriva del BRD y del diseño de U3. El paquete del profesor
(`INSTRUCCIONES_ALUMNO.txt`) es un *modelo de pruebas propuesto*: entra por un adaptador en
infraestructura y no contamina el dominio. Todo lo que el BRD no respalda se marca como
**extensión del paquete**.

Versión vigente de los artefactos: BPMN, US20, glosario y BRD se toman **con las correcciones
de la sección C** (no se rehacen los documentos; este registro es la fuente).

## A. Decisiones sobre el paquete de pruebas

| ID | Decisión | Origen |
|---|---|---|
| D-01 | La **Cita** es la raíz del agregado. Operación = Cita; recurso = ServicioVeterinario; actor = Propietario; línea = ServicioSolicitado (servicio + cantidad). | Informe U3 + mapeo del paquete |
| D-02 | Importe = `Money` MXN con `Decimal`, 2 decimales, `ROUND_HALF_UP`. Total = Σ precio × cantidad. | Glosario #8, US10, BPMN (extensión: sin NB en el BRD, ver A-02) |
| D-03 | `PuedeProcesarse = ActorActivo AND DetalleNoVacio AND Autorizada`. | Paquete (regla 1) + R-09, NB-20 |
| D-04 | La validación de líneas (servicio habilitado, cantidad entera ≥ 1, capacidad) es independiente de la elegibilidad y se reporta aparte. | Decisión técnica |
| D-05 | `BeneficioDeReferencia = Preferente AND Total ≥ 1500 AND NOT Promoción`. Solo elegibilidad; umbral configurable. | **Extensión del paquete** |
| D-06 | Specifications con respaldo del BRD: `AtencionPermitida = TieneCita OR EsEmergencia` (R-06); `SeguimientoCalculable = EsquemaValidado AND RequiereRefuerzo`, y NOT para seguimiento pendiente (R-12, R-13, ADR-05). | BRD + ADR-05 |
| D-07 | Máquina de estados de la Cita: SOLICITADA → CONFIRMADA → REALIZADA. Cancelar desde SOLICITADA o CONFIRMADA. REALIZADA y CANCELADA son terminales. | BPMN + NB-08 (corrige el flujo literal del paquete) |
| D-08 | Capacidad: se verifica y consume al **confirmar**. Cancelar libera. Realizar mantiene el consumo. | Q3 del BRD + decisión técnica |
| D-09 | El importador reconstituye las 60 operaciones tal cual (incluidas las inválidas). Las reglas se aplican al ejecutar casos de uso. Crear por API exige invariantes. | Decisión técnica |
| D-10 | Una mascota sintética por tutor (40), marcada como fixture. `veterinario_disponible` no se implementa (sin datos ni respaldo en el BRD). | R-10, ADR-02 |
| D-11 | `aprobar` = confirmar; `completar` = confirmar y luego realizar; `cancelar` = cancelar; `repetir_aprobacion` = confirmar dos veces; `saltar_estado` = realizar desde SOLICITADA (inválido). | Interpretación del paquete — **confirmar con el profesor** |
| D-12 | Orden de evaluación: primero validez de la transición, luego guardas. Confirmar exige elegibilidad, líneas válidas y capacidad. Cancelar y realizar solo exigen el estado correcto. | Decisión técnica |
| D-13 | HTTP: 200/201 éxito; 400 payload mal formado; 403 rol no autorizado; 404 no existe; 409 transición inválida o capacidad insuficiente; 422 regla de negocio no cumplida. | Contrato del equipo |
| D-14 | Eventos: `CitaAgendada`, `CitaRealizada`, `CitaCancelada`, `CitaModificada`, `NotaClinicaRegistrada`, `VacunacionRegistrada`, `HospitalizacionIniciada`, `EmergenciaIdentificada`. Despacho síncrono tras el commit; se guardan en `eventos_dominio`. | Informe + P6 |
| D-15 | Oráculo independiente: evalúa el texto de cada regla sobre las filas del CSV, sin importar el dominio. | "No inventar resultados esperados" |

## B. Alcance, ADR y permisos

- **Alcance:** CU-01 completo con los CSV; CU-02, CU-03 y CU-05 hasta API y pruebas; CU-04 solo hasta el inicio de la hospitalización.
- **P1–P7:** P1 puerto de catálogo; P2 aceptada (ADR-05); P3 aceptada (`mascotaId` opcional en Emergencia); P4 y P5 sin asociaciones; P6 por D-14; P7 por ADR-04.
- **ADR:** ADR-01 a ADR-05 → *Aceptada*. Nuevos: ADR-06 (stack), ADR-07 (máquina de estados y capacidad), ADR-08 (adaptador del paquete).
- **Permisos (por validar):** Recepción: propietarios, mascotas, solicitar/modificar/confirmar/cancelar citas, llegada, identificar emergencia. Veterinario: notas, vacunación, realizar cita, orden de hospitalización. Personal clínico: iniciar hospitalización y seguimiento. Responsable: reportes. El rol viaja en el encabezado `X-Rol`.
- **Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL 16, pytest + pytest-cov (≥ 80 %), Docker Compose (`db`, `app`, `tests`), GitHub Actions.

## C. Ambigüedades del diagnóstico y su resolución

| # | Decisión |
|---|---|
| A-01 | Emergencia: la identifica Recepción y notifica al veterinario; el personal clínico la atiende. (US20 pasa a actor Recepción.) |
| A-02 | Importe: entra el cálculo del total. Cobro y facturación fiscal quedan fuera. Addendum al BRD: NB-22. |
| A-03 | El Propietario no es usuario del sistema; Recepción opera en su nombre (R-01, Q4). Usuarios: Recepción, Veterinario, Personal clínico, Responsable. |
| A-04 | Alergias en Mascota: las captura Recepción y las consulta el veterinario. R-03 protege solo las notas clínicas. |
| A-05 | Recordatorios: solo de vacunas, calculados por consulta, sin envío. Los de citas quedan diferidos. |
| A-06 | Modificar cita: permitido en SOLICITADA y CONFIRMADA; no cambia el estado; revalida capacidad; emite `CitaModificada`. |
| A-07 | El BPMN vigente incluye vacunación, modificar cita y el flujo de emergencia hacia el veterinario. |
| A-08 | Esquema de vacunación: ADR-05(b), catálogo propio, fixtures sintéticos en pruebas. |
| A-09 | Personal clínico y Veterinario son roles separados, sin herencia. Glosario: personal clínico = técnicos y auxiliares. |
| A-10 | Signos vitales, dosis y lotes: atributos opcionales sin reglas. Hoja de monitoreo (US18/US19) fuera del código. |
| A-11 | Sin horarios ni duraciones en los datos, `PeriodoDeCita` no se implementa. NB-07 = "diferido por falta de datos" en la matriz. |

## D. Riesgos abiertos

1. D-11 (`completar`) y D-08 (momento de consumo de capacidad) son interpretaciones; quedan aisladas (adaptador y un servicio de dominio) para que cambiarlas sea barato.
2. No hay oráculo oficial: se deriva de las reglas del paquete y de los requerimientos (D-15).

## E. Decisiones de la Etapa 2 (importador y oráculo)

| ID | Decisión |
|---|---|
| E-01 | El importador (`infrastructure/csv_loader.py`) lee los CSV tal cual (D-09). Solo rechaza archivos dañados: columnas distintas, valores ilegibles, ids repetidos, claves foráneas rotas o transiciones cuyo estado inicial no coincide con la operación. |
| E-02 | El oráculo (`tests/oraculo.py`) evalúa el **texto** de `regla_a_verificar` (NOT > AND > OR). Una condición que no conoce lanza `ReglaDesconocida`; no se inventa. |
| E-03 | Equivalencias del texto a los datos: "cliente activo" = `actores.activo`; "VIP" = `actores.es_preferente`; "autorizacion" = `operaciones.autorizado`; "promocion" = `operaciones.promocion_activa`; "detalle no vacio" = al menos una línea; "total >= N" = total en `Decimal` ≥ N. |
| E-04 | Cada caso de transición es independiente: parte de la capacidad inicial del catálogo y de SOLICITADA. |
| E-05 | Una acción de varios pasos no es atómica: si el segundo paso falla, el primero se conserva (p. ej. `repetir_aprobacion` termina en CONFIRMADA con `TransicionInvalida`). |
| E-06 | Los eventos esperados: confirmar → `CitaAgendada`; realizar → `CitaRealizada`; cancelar → `CitaCancelada`. |

**Resultados esperados derivados (evidencia en `docs/evidencia/`):**
validar_operacion 43 CUMPLE / 17 NO_CUMPLE; evaluar_beneficio 9 / 51;
transiciones: 6 OK, 6 `TransicionInvalida`, 8 `PrecondicionNoCumplida`.
No son un oráculo oficial del profesor: se derivan de las reglas del paquete y de D-07 a D-12.

## F. Decisiones de la Etapa 3 (dominio)

| ID | Decisión |
|---|---|
| F-01 | **Dos formas de obtener una Cita:** `Cita.solicitar(...)` crea una cita nueva y aplica las reglas de negocio (D-09: ≥ 1 línea, servicios existentes y habilitados, mascota del propietario). El constructor `Cita(...)` reconstituye datos existentes y solo valida la estructura, porque los CSV traen casos que hoy se rechazarían. |
| F-02 | `ServicioSolicitado` siempre exige cantidad entera ≥ 1 (no existe una línea con cantidad 0). Un dato con cantidad inválida se reporta como `ErrorDeDatos` al importar. |
| F-03 | **Sin precio congelado en la línea:** el total se calcula con el precio vigente del catálogo, igual que el oráculo (D-02). Si el BRD pide conservar el precio histórico, se agrega después. |
| F-04 | `Money` solo admite `Decimal`, `int` o `str` (nunca `float`), no admite negativos y redondea a 2 decimales con `ROUND_HALF_UP`. |
| F-05 | Invariante de pertenencia (R-10): una cita nueva solo puede usar una mascota del mismo propietario (`MASCOTA_AJENA`). |
| F-06 | `autorizada` se pasa de forma explícita al crear una cita; no se asume un valor por omisión porque el BRD no define la autorización. `promocion_activa` y `Propietario.preferente` son extensiones del paquete (D-05). |
| F-07 | Códigos de error estables (`InvarianteViolada.codigo`): `DETALLE_VACIO`, `SERVICIO_DESHABILITADO`, `SERVICIO_INEXISTENTE`, `CANTIDAD_INVALIDA`, `MASCOTA_AJENA`, `PESO_INVALIDO`, `CAPACIDAD_INVALIDA`, `MONTO_INVALIDO`, entre otros. Los nombres coinciden con los motivos del oráculo. |
| F-08 | La entidad `Mascota` conserva peso y alergias (NB-04, NB-05, A-04). El adaptador del paquete crea una mascota fixture por propietario (D-10), con especie "Fixture". |
| F-09 | Las Specifications (Etapa 4), la máquina de estados (Etapa 5) y los eventos (Etapa 6) se construyen sobre este modelo. `EstadoCita` ya existe; `Cita` aún no expone transiciones. |

**Verificación cruzada:** los 60 totales calculados por el dominio (`Money`) coinciden con los del oráculo independiente (`tests/test_adaptador_paquete.py`).

## G. Decisiones de la Etapa 4 (Specifications)

| ID | Decisión |
|---|---|
| G-01 | Patrón genérico en `domain/specification.py`: `Specification[T]` con `And` (`&`), `Or` (`\|`) y `Not` (`~`). Cada una responde `es_satisfecha_por` y explica `motivos_de_incumplimiento`. |
| G-02 | Las reglas evalúan un `CitaEnContexto` (cita + propietario + catálogo + capacidad disponible). El contexto exige que el propietario sea el de la cita (`PROPIETARIO_INCORRECTO`). |
| G-03 | Los códigos de motivo coinciden con los del oráculo (`ACTOR_INACTIVO`, `DETALLE_VACIO`, `NO_AUTORIZADA`, `SERVICIO_DESHABILITADO:<id>`, `CAPACIDAD_INSUFICIENTE:<id>`). |
| G-04 | Un servicio sin disponibilidad registrada cuenta como 0 disponible (falla cerrado, nunca abierto). |
| G-05 | Cancelar y modificar solo exigen "no finalizada" (NOT (REALIZADA OR CANCELADA)), no dependen de la elegibilidad del propietario (D-12). |
| G-06 | Las Specifications de D-06 (`AtencionPermitida`, `SeguimientoCalculable`) esperan a que existan Emergencia y Vacunación en el dominio. |

**Specifications implementadas y su respaldo:**

| Regla | Composición | Respaldo |
|---|---|---|
| `puede_procesarse` | ActorActivo AND DetalleNoVacio AND Autorizada | D-03, R-09, NB-20 |
| `puede_confirmarse` | puede_procesarse AND ServiciosHabilitados AND CapacidadSuficiente | D-08, D-12 |
| `beneficio_de_referencia` | PropietarioPreferente AND TotalMinimo AND NOT PromocionActiva | D-05 (extensión del paquete) |
| `esta_finalizada` | EnEstado(REALIZADA) OR EnEstado(CANCELADA) | D-07 |
| `puede_cancelarse` / `puede_modificarse` | NOT esta_finalizada | NB-08, A-06, D-07 |

**Verificación cruzada con el oráculo:** las reglas coinciden en los 120 casos y los motivos de `puede_confirmarse` coinciden en las 60 operaciones (`tests/test_reglas_cita.py`).

## H. Decisiones de la Etapa 5 (máquina de estados y capacidad)

| ID | Decisión |
|---|---|
| H-01 | `domain/ciclo_de_vida.py` define la tabla `TRANSICIONES` (estado + acción → estado destino) como **única fuente de verdad**. Las Specifications `puede_cancelarse` y `puede_modificarse` se verifican contra esa tabla en las pruebas, para que no puedan contradecirse. |
| H-02 | Acciones: `confirmar`, `realizar`, `cancelar` y `modificar`. `modificar` es una transición de un estado a sí mismo (A-06) y solo es válida en SOLICITADA y CONFIRMADA. |
| H-03 | Orden de evaluación (D-12): primero `TransicionInvalida` (409) si la acción no existe desde ese estado; después `PrecondicionNoCumplida` con los motivos. Solo `confirmar` y `modificar` de una cita confirmada tienen condiciones. |
| H-04 | La capacidad es un objeto propio (`Disponibilidad`): `reservar` y `liberar` son todo o nada, y nunca baja de cero ni libera más de lo reservado. Confirmar reserva; cancelar desde CONFIRMADA libera; cancelar desde SOLICITADA no toca nada; realizar no libera (D-08). |
| H-05 | Modificar una cita CONFIRMADA revisa que la demanda nueva quepa sumando lo que la cita ya tenía reservado. Si no cabe, no cambia nada. Si cabe, libera lo anterior y reserva lo nuevo. |
| H-06 | El estado y las líneas de la `Cita` no se cambian desde fuera: solo el servicio de ciclo de vida puede hacerlo, así toda transición pasa por la máquina. |
| H-07 | Códigos HTTP previstos para la API (D-13): `TransicionInvalida` → 409; `PrecondicionNoCumplida` con `CAPACIDAD_INSUFICIENTE` → 409; las demás precondiciones → 422. |
| H-08 | La API responde con el estado final de la cita; los eventos de dominio de cada transición se agregan en la Etapa 6. |

**Hallazgo sobre los datos:** al confirmar las 60 operaciones en orden con capacidad compartida, 38 quedan CONFIRMADA y 22 se rechazan, **ninguna por capacidad**. Las dos que habrían rebasado el cupo (O035 en VET-P016 y O050 en VET-P001) ya se rechazan antes por servicio deshabilitado y tutor inactivo. Por eso la capacidad acumulada se prueba con casos propios (`tests/test_ciclo_de_vida.py`) y no solo con los CSV.

**Verificación cruzada con el oráculo:** las 20 transiciones del dominio coinciden con el oráculo en estado final, excepción y motivos, y la confirmación secuencial de las 60 citas coincide con `confirmar_en_secuencia` (evidencia en `docs/evidencia/oraculo_secuencia.csv`).

## I. Decisiones de la Etapa 6 (Domain Events)

| ID | Decisión |
|---|---|
| I-01 | Eventos implementados (`domain/eventos.py`): `CitaAgendada` (al confirmar), `CitaRealizada`, `CitaCancelada` y `CitaModificada`. Son inmutables, están en pasado y llevan fecha y hora **con zona horaria** (`EVENTO_SIN_ZONA_HORARIA` si falta). |
| I-02 | Los eventos de Vacunación, Emergencia, Hospitalización y Nota clínica (D-14) se agregan cuando existan esas entidades en el dominio. |
| I-03 | La `Cita` acumula sus eventos pendientes y los entrega una sola vez con `extraer_eventos()`. Una acción rechazada no emite eventos. |
| I-04 | El reloj se inyecta en `CicloDeVidaDeCita` (por omisión, UTC) para probar con horas fijas. |
| I-05 | Contenido: `CitaAgendada` incluye servicios y total; `CitaCancelada` incluye `estado_anterior` (indica si se liberó capacidad); `CitaModificada` incluye lo anterior y lo nuevo. |
| I-06 | Despacho (`application/despachador.py`): síncrono, **después** de guardar los cambios. Un manejador que falla no deshace lo guardado ni impide a los demás: queda en `despachador.fallos` y en el log. |
| I-07 | `RegistroDeEventos` guarda cada evento con un número de secuencia; en la Etapa 7 se persistirá en la tabla `eventos_dominio` (D-14). `a_diccionario()` deja el evento listo para JSON. |
| I-08 | No hay consumidores de negocio (P6): los eventos se publican y se registran. |

**Verificación cruzada con el oráculo:** los eventos de las 20 transiciones del dominio coinciden con los del oráculo, y los 38 `CitaAgendada` de la confirmación secuencial corresponden, en orden, a las citas que el oráculo da por confirmadas y con el mismo total. Evidencia en `docs/evidencia/dominio_eventos.csv`.

## J. Decisiones de la Etapa 7 (aplicación y persistencia)

| ID | Decisión |
|---|---|
| J-01 | **Enmienda al ADR-06:** la persistencia usa SQL explícito con `psycopg` (PostgreSQL) y el mismo código se prueba contra SQLite. Reemplaza a SQLAlchemy + Alembic. Motivo: poder verificar toda la lógica de persistencia sin depender del motor real, y que el equipo vea y entienda cada consulta. El esquema se crea con `crear_esquema` (idempotente). |
| J-02 | Los puertos (`application/puertos.py`) definen qué necesita la aplicación; `infrastructure/repositorios_sql.py` los implementa. Los casos de uso no conocen SQL. |
| J-03 | Esquema: importes en **centavos enteros** (sin pérdida de precisión), booleanos como 0/1, fechas y horas como texto ISO 8601, líneas de la cita en `cita_lineas` con su posición. Las llaves foráneas y los `CHECK` repiten en la base los invariantes del dominio. |
| J-04 | **La capacidad no se guarda:** se reconstruye en cada operación como catálogo menos la demanda de las citas CONFIRMADA y REALIZADA (D-08). Así no existe un contador que pueda desfasarse de las citas. |
| J-05 | Una operación = una Unidad de Trabajo: la cita y sus eventos se guardan en la **misma transacción** (`eventos_dominio`) y los eventos se **publican después del commit** (D-14). Sin `commit()` se deshace todo. |
| J-06 | Control de acceso por rol (`application/control_de_acceso.py`, ADR-04): Recepción registra y gestiona citas; Veterinario realiza y consulta; Responsable consulta; Personal clínico sin permisos sobre citas hasta CU-04. Es una propuesta del equipo (P7) por validar. |
| J-07 | `python -m vetcare24.infrastructure.sembrado` carga los CSV tal cual (D-09) solo si la base está vacía. |
| J-08 | Las pruebas de persistencia corren en SQLite siempre y en PostgreSQL cuando `DATABASE_URL` apunta a uno (Docker Compose y CI). |
| J-09 | `X-Rol` (Etapa 8) viajará en el encabezado; la autenticación sigue fuera del dominio (ADR-04). |

**Limitación conocida (concurrencia):** si dos recepcionistas confirman al mismo tiempo citas que compiten por la última unidad de capacidad, ambas podrían confirmarse, porque la reconstrucción de capacidad y el guardado no están bloqueados. La mitigación en producción sería bloquear las filas de `servicios` (`SELECT ... FOR UPDATE`) dentro de la transacción de confirmación; queda como mejora fuera del alcance del PIA y se menciona en el reporte.

**Verificación cruzada con el oráculo:** al confirmar las 60 citas a través de los casos de uso y la base de datos, los motivos coinciden con `confirmar_en_secuencia`, hay 38 citas CONFIRMADA y 38 eventos `CitaAgendada` guardados en `eventos_dominio`, en el mismo orden.

## K. Decisiones de la API REST (cierre de la Etapa 7)

| ID | Decisión |
|---|---|
| K-01 | La API (`api/rutas.py`) solo traduce HTTP a un caso de uso y de vuelta; no contiene reglas de negocio. Endpoints de CU-01: `GET /servicios`; `POST /propietarios`, `GET /propietarios/{id}`; `POST /mascotas`, `GET /mascotas/{id}`; `POST /citas`, `GET /citas` (filtros `estado`, `propietario_id`), `GET /citas/{id}`, `PUT /citas/{id}/servicios`, `POST /citas/{id}/confirmar`, `/realizar`, `/cancelar`. |
| K-02 | El rol viaja en `X-Rol` (J-09; ADR-04: la autenticación sigue fuera del dominio). Sin encabezado: **401**; valor desconocido: **400**; no distingue mayúsculas. Los permisos los decide `control_de_acceso` (403). *Cierra J-09, que lo ubicaba en "Etapa 8".* |
| K-03 | Códigos HTTP según D-13/H-07: 200/201 éxito; **400** solicitud mal formada (se reemplaza el 422 que FastAPI usa por omisión); 403 sin permiso; 404 no existe; 409 transición inválida, capacidad insuficiente o duplicado; **422** regla de negocio no cumplida (incluye toda `InvarianteViolada`, con su código estable). |
| K-04 | Todos los errores tienen la misma forma: `{"error": {"codigo", "mensaje", "detalles"}}` (`api/errores_http.py`, función pura probada sin servidor). `codigo` es corto y estable (para programas); `mensaje` es una frase en español lista para mostrarse al cliente (p. ej. "No se puede confirmar la cita: no hay capacidad suficiente para el servicio S1."). `detalles` solo lista los campos inválidos de una solicitud mal formada, también en español. |
| K-05 | Los importes viajan como texto decimal (`"300.00"`, D-02). `total_mxn` de una cita se calcula con el precio vigente del catálogo. |
| K-06 | `create_app(database_url, preparar_esquema=True)`: al arrancar crea las tablas que falten (idempotente, J-01). Los servicios y el registro de eventos viven en `app.state`; cada operación abre su propia Unidad de Trabajo. |
| K-07 | **Fuera de alcance** (asuntos menores): consulta de eventos por HTTP, paginación de `GET /citas`, autenticación real, bloqueo de concurrencia (limitación ya registrada en J) y los casos de uso de hospitalización (CU-04). |


## L. Revisión de la API (cierre de la Etapa 8)

La API de la sección K se revisó y se conservó tal cual en sus decisiones (K-02 a K-04: 401 sin rol, 400 rol desconocido, formato `{"error": {...}}`). Se agregó lo que faltaba para cumplir los requisitos del PIA y se corrigieron cuatro puntos.

| ID | Decisión |
|---|---|
| L-01 | **Evaluaciones:** `GET /citas/{id}/evaluaciones/procesamiento` y `/beneficio` responden 200 con `{regla, cumple, motivos}` y no modifican nada. Son la forma de ejecutar por HTTP los 120 casos de prueba (D-03, D-05). Corrige K-07. |
| L-02 | **Eventos:** `GET /eventos` lista los eventos de dominio guardados (D-14), para verificar por HTTP los de las 20 pruebas de transición. Corrige K-07. |
| L-03 | **Motivos legibles por programas:** todo error trae `error.motivos` (por ejemplo `["ACTOR_INACTIVO"]`, `["CAPACIDAD_INSUFICIENTE:S1"]`, `["realizar desde SOLICITADA"]`). Es un campo nuevo; el resto del formato no cambia. |
| L-04 | **Mismo formato en 404 y 405 de FastAPI** (`RUTA_NO_ENCONTRADA`, `METODO_NO_PERMITIDO`) y en un JSON roto (400). Antes devolvían `{"detail": ...}`, lo que contradecía K-04. |
| L-05 | **Tipos estrictos en la entrada:** `cantidad` solo acepta enteros y los campos booleanos solo aceptan `true`/`false`. Antes `"2"` y `true` se aceptaban y se convertían en silencio. |
| L-06 | **Importes como texto en el contrato:** `precio_mxn`, `total_mxn` y `peso_kg` son `string` en OpenAPI (antes aparecían como número o texto, ambiguo). |
| L-07 | **Los importes de la respuesta usan `ServicioDeCitas.catalogo()`**, sin permiso propio, en lugar de consultar el catálogo con el rol de quien opera. Así, una acción ya guardada nunca termina en un 403 al armar la respuesta si la matriz de permisos cambia. |
| L-08 | **Modelo de error documentado:** `ErrorOut` describe `codigo`, `mensaje`, `detalles` y `motivos` en OpenAPI (antes era un objeto genérico). |
| L-09 | **Recorrido por la API:** `tests/api_paquete.py` ejecuta por HTTP los 120 casos, las 20 transiciones y la confirmación de las 60 citas y los compara con el oráculo. `python -m tests.evidencia_api` genera `api_casos.csv` y `api_transiciones.csv`; `python -m vetcare24.api.exportar_openapi` exporta el contrato. |

**Verificación cruzada:** el recorrido completo por la API coincide con el oráculo (120/120 casos, 20/20 transiciones con la distribución 200 ×6, 409 ×6, 422 ×8, y 38 de 60 confirmaciones).

## M. Decisiones de la Etapa 9 (Vacunación, CU-03)

| ID | Decisión |
|---|---|
| M-01 | **`Vacunacion` es un agregado por cada aplicación** (P2, tabla de entidades): id, mascota, vacuna, fecha y lote opcional. El historial de una mascota es el conjunto de sus `Vacunacion`. El repositorio solo **agrega y lee**: nada se modifica ni se borra (R-11, NB-14). |
| M-02 | **Registrar nunca depende del esquema** (ADR-05, opción b). Sin esquema, o con uno sin validar, el registro se guarda igual y el seguimiento queda `pendiente_de_esquema`; no es un error. |
| M-03 | **`EsquemaDeVacunacion`**: por tipo de vacuna, `frecuencia_dias` (de 1 a 36,500), `requiere_refuerzo` y `validado`. Es un concepto de referencia, consultado en solo lectura por los casos de uso. |
| M-04 | **Fórmula de seguimiento (PROPUESTA por validar con el stakeholder):** `próxima aplicación = fecha de la última aplicación + frecuencia_dias del esquema`, y `es_refuerzo = requiere_refuerzo`. El BRD (Q10) dice que se usa el esquema pero no da la fórmula; esta es la más simple compatible con él. Los esquemas con que se prueba son **ejemplos sin valor clínico** (`VAC-ANUAL`, `VAC-REFUERZO-30D`, `VAC-SIN-VALIDAR`). |
| M-05 | **Corrección a D-06 / G-06:** `SeguimientoCalculable = EsquemaValidado AND RequiereRefuerzo` estaba mal planteada, porque una vacuna sin refuerzo nunca tendría seguimiento. R-12 pide un esquema "definido **y** validado": `seguimiento_calculable = EsquemaDefinido AND EsquemaValidado`; `seguimiento_pendiente = NOT seguimiento_calculable`; `RequiereRefuerzo` (R-13) es una pregunta aparte. |
| M-06 | El seguimiento **no se guarda**: se calcula en cada consulta a partir del historial (informe, CU-03; A-05). La última aplicación de cada tipo manda; si hay dos el mismo día, la de id mayor. |
| M-07 | **Mismo tipo de vacuna aunque cambien mayúsculas o espacios** (`Rabia`, ` rabia `): se compara por una clave normalizada. Un esquema por tipo; la base rechaza repetirlo. |
| M-08 | **Recordatorios (NB-17, A-05):** `GET /vacunas/proximas` lista las vacunas vencidas o que vencen en los próximos `dias`, con mascota, propietario y vacuna. **No se envía nada**: el canal no está definido en el BRD. |
| M-09 | **Permisos (por validar, P7):** solo el Veterinario registra vacunas. Recepción, Veterinario y Responsable las consultan (Recepción, por los recordatorios). Personal clínico sigue sin permisos hasta CU-04. |
| M-10 | **Evento `VacunacionRegistrada`** (D-14): no dice que se calculó o envió un recordatorio. Cada evento declara qué agregado lo emitió: `eventos_dominio` guarda `agregado_tipo` y `agregado_id` en lugar de `cita_id` (se conserva `cita_id` en la lectura para los eventos de citas). |
| M-11 | **Cambio de esquema de base de datos:** `eventos_dominio` cambió de columnas. No hay migración: si la base de desarrollo tiene la versión anterior, la aplicación avisa y se reinicia con `docker compose down -v` y se vuelve a cargar (`sembrado`). |
| M-12 | No se valida que la fecha de aplicación no sea futura ni que no se repita la misma vacuna el mismo día: el BRD no lo dice. |

**Qué no cubre:** ni los CSV del profesor ni el BRD traen datos de vacunación, así que los resultados esperados de las pruebas se derivan de los requerimientos (R-11, R-12, R-13, NB-14 a NB-17) y de las decisiones anteriores, no de un oráculo oficial.

## N. Decisiones de la Etapa 10 (Emergencias, CU-05)

Fuente: informe de arquitectura (Unidad 3): tabla de servicios (CU-05), agregado Emergencia,
P3, Unit of Work y matriz de trazabilidad (NB-19); BRD: NB-19, R-06, S-08, CR-8, US20.

| ID | Decisión |
|---|---|
| N-01 | **`Emergencia` es un agregado raíz** (informe): id, motivo, `identificada_en`, estado, `mascota_id` **opcional** (P3) y `datos_paciente` (texto libre con los datos disponibles del paciente y del propietario, para cuando la mascota no está registrada). Fechas y horas con zona horaria. El constructor reconstituye; una emergencia nueva se crea con `CicloDeVidaDeEmergencia.identificar` (como F-01). |
| N-02 | **Máquina de estados:** `IDENTIFICADA → EN_ATENCION` con la acción `iniciar_atencion` del personal clínico (A-01, US20). La tabla `TRANSICIONES` es la única fuente de verdad (H-01). El cierre de la emergencia queda **fuera de alcance**: no está definido en el BRD ni en el informe. |
| N-03 | **Nombres del informe:** el caso de uso es `atender_emergencia` (`AtenderEmergenciaComando`): registra la emergencia **sin cita** (R-06), activa el protocolo y notifica al veterinario. Registrar ES activar el protocolo (BPMN «¿Es una emergencia?» → «Protocolo de Emergencia»); los criterios clínicos de activación siguen pendientes (CR-8). Por eso el paso del personal clínico se llama `iniciar_atencion`, para no confundirlo. El comando no acepta un id de cita (400 si se envía). |
| N-04 | **Datos mínimos (PROPUESTA):** solo el motivo es obligatorio (`MOTIVO_VACIO`, 422). El informe deja pendientes los datos obligatorios; pedir menos es lo seguro en una emergencia. Si se envían `datos_paciente`, no pueden estar en blanco. |
| N-05 | **Sin límite de emergencias por mascota:** ni el BRD ni el informe lo restringen. Mientras no exista el cierre, toda emergencia registrada cuenta como activa. |
| N-06 | **Eventos:** `EmergenciaIdentificada` (D-14) al registrar, guardado en `eventos_dominio` en la misma transacción y publicado después del commit (J-05). `iniciar_atencion` no emite evento: D-14 no lo define (se agregaría `EmergenciaAtendida` si el equipo lo valida). |
| N-07 | **Permisos (A-01; P7 y CR-8 por validar):** Recepción registra (A-01: la identifica); el personal clínico inicia la atención; los cuatro roles consultan (el veterinario recibe el aviso). Cierra el pendiente de J-06 ("Personal clínico sin permisos"). |
| N-08 | **Notificación al veterinario (informe):** puerto de salida `NotificadorDeVeterinario`. Se llama **después** de confirmar el registro (`test_notifica_veterinario_tras_confirmar`). Si falla, el registro **no se deshace**: la respuesta trae `notificacion: pendiente_de_notificar` (Unit of Work del informe). El BRD no define el canal: la implementación `BandejaDeAvisos` deja el aviso en el log y en una bandeja en memoria, consultable en `GET /avisos-veterinario`; se vacía al reiniciar. Los avisos pendientes no se reintentan (mejora fuera de alcance). |
| N-09 | **Specification con OR (cierra G-06 y D-06):** `atencion_permitida = TieneCitaConfirmada OR TieneEmergenciaActiva` (R-06). Una cita cuenta solo si está CONFIRMADA (programada, I-01). Se expone como consulta: `GET /mascotas/{id}/evaluaciones/atencion` → `{regla, cumple, motivos}` (como L-01). |
| N-10 | **Base de datos:** tabla nueva `emergencias` con `CHECK` y llave foránea **opcional** a `mascotas`. No hace falta reiniciar la base de la Etapa 9: `crear_esquema` agrega la tabla y conserva los datos. `eliminar_esquema` usa `CASCADE` en PostgreSQL, para que una tabla de otra versión que apunte a `mascotas` no bloquee el reinicio de la base de pruebas. |
| N-11 | **API:** `POST /emergencias` (201, con `protocolo_activado` y `notificacion`), `POST /emergencias/{id}/iniciar-atencion` (200), `GET /emergencias/{id}`, `GET /emergencias` (filtros `estado` y `mascota_id`), `GET /mascotas/{id}/evaluaciones/atencion` y `GET /avisos-veterinario`. Iniciar dos veces: 409 `TRANSICION_INVALIDA`. Los errores de transición ahora nombran la entidad (`entidad`, por omisión `"cita"`): los mensajes de las citas no cambian. |
| N-12 | **Evidencia:** 20 escenarios por HTTP (`tests/api_emergencias.py`, E01 a E20) recorren todos los códigos del contrato. Sus resultados esperados se derivan de NB-19, R-06, US20, A-01 y N-01 a N-11, porque no hay oráculo oficial. `python -m tests.evidencia_emergencias` escribe `docs/evidencia/api_emergencias.csv` y termina con error si alguno no coincide. |
| N-13 | **CI/CD:** el job `lint` de la Etapa 9 fallaba (`ruff check .`: tres bloques de importaciones desordenados y una variable de ciclo sin enlazar en `tests/test_ciclo_de_vida.py`). Se corrigió. El job `test` ahora también genera la evidencia y la publica como artefacto `evidencia`. |

**Qué no cubre:** el cierre de la emergencia, los criterios clínicos de activación (CR-8), el reintento de avisos pendientes y asociar después la emergencia a una mascota que se registre más tarde.

**Verificación:** 574 pruebas pasan en SQLite y PostgreSQL 16, con 98.8 % de cobertura. El recorrido de CU-05 coincide en 20 de 20 escenarios, y los 120 casos y las 20 transiciones del paquete siguen coincidiendo con el oráculo.

