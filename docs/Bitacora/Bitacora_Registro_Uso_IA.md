# Bitácora de uso de inteligencia artificial · Unidad 5

**Curso:** Componentes de Lógica de Negocios · **Equipo 4** · **Fecha:** 05/11/2026
**Integrantes:** García Cerda Randal Guillermo · Sarmiento Hernández Cesar Martín · Torres Pasillas Angela Susana

## 1. Herramienta

- Asistente de IA: Claude (Anthropic), usado como asistente de trabajo con acceso a un espacio de ejecución aislado, sin acceso a la computadora del equipo y sin conexión a internet.
- Alcance: apoyo para documentar, organizar y revisar el trabajo de la Unidad 5. Las ejecuciones en la computadora del equipo (PowerShell, Docker, GitHub) las hizo el equipo.

> Esta bitácora se redactó a partir de la conversación de trabajo con la herramienta. Los campos marcados como «[completar]» los debe llenar el equipo.

## 2. Registro de actividades

| # | Actividad | Qué se pidió | Qué entregó la IA | Qué verificó o decidió el equipo |
|---|---|---|---|---|
| 1 | Laboratorio guiado completado | Llenar el laboratorio guiado con las capturas de cada paso | Clasificó y verificó las capturas, redactó las explicaciones y armó el documento de 81 páginas | El equipo ejecutó cada paso y aportó las capturas. Se corrigieron lecturas erróneas de duraciones de CI y se suavizaron afirmaciones que las capturas no demostraban |
| 2 | Reporte técnico | Documentar procedimiento, evidencias, resultados y matriz de prueba | Redactó el reporte, las tablas de reglas, casos, distribución y evidencias, y el índice de figuras | El equipo revisó el contenido y pidió el cambio de formato |
| 3 | Reporte en el formato del profesor | Pasar el reporte a la plantilla del profesor, con redacción narrativa y sin mencionar el nombre interno del proyecto | Reescribió el documento en la plantilla (78 páginas) y luego en tono formal, a petición del equipo | El equipo revisó el tono y solicitó el ajuste a un estilo formal |
| 4 | Estructura del repositorio | Preparar el repositorio de entrega según el repositorio de ejemplo | Armó la estructura de carpetas, el README, el flujo de integración continua, las matrices en CSV y Excel y el script de pruebas | El equipo comparó con el ejemplo y decidió el contenido; los documentos de las unidades 2 y 3 los agrega el equipo |
| 5 | Protección de la rama `main` | Saber cómo proteger la rama y demostrarlo | Indicó los pasos en GitHub y cómo provocar el rechazo del push | El equipo creó el conjunto de reglas, intentó el push directo y capturó el rechazo |
| 6 | Reportes de cobertura | Obtener el HTML de cobertura de ambos proyectos | Dio los comandos, identificó que dos archivos enviados no eran el reporte (un `coverage.xml` y el paquete `coverage` del entorno virtual) y validó el HTML correcto | El equipo generó los reportes en su computadora (laboratorio 100 %, VetCare 24 99 %) |
| 7 | Corrida de todas las pruebas | Correr todas las pruebas de una vez | Escribió el script `ejecutar_todas_las_pruebas.ps1` | El equipo lo ejecutó: VetCare 24 con 584 pruebas pasando y 98.81 %; laboratorio con 32 pruebas y 100 % |
| 8 | Corrección de Ruff | Resolver el fallo de Ruff en el laboratorio | Indicó el comando de corrección automática | El equipo ejecutó `ruff check --fix` y comprobó que quedó limpio |

## 3. Qué hizo la IA y qué hizo el equipo

La IA redactó textos, organizó archivos y calculó o contrastó cifras contra las capturas. El equipo ejecutó los comandos, generó las evidencias, creó el repositorio y la regla de protección, decidió el contenido final y es responsable de lo entregado.

## 4. Límites y errores detectados

- La IA no ejecutó Docker, PowerShell ni GitHub en la computadora del equipo; las cifras de pruebas y cobertura provienen de las capturas y corridas del equipo.
- Algunas lecturas iniciales de las capturas fueron incorrectas (duraciones de los trabajos de CI) y se corrigieron al contrastarlas.
- El script de pruebas no venía en la primera versión del paquete entregado y el equipo lo pidió por separado.
- La IA no pudo correr las pruebas que dependen de SQLAlchemy; el equipo las corrió y confirmó 32 pruebas en el laboratorio.
- El reporte de cobertura del laboratorio incluido en el repositorio corresponde a la corrida de 20 pruebas; la corrida final de 32 está en la Figura 88.

## 5. Verificación humana

- Todas las capturas son de ejecuciones reales del equipo.
- No se incluyeron tokens, entornos virtuales ni credenciales. El token de GitHub se escribió en la terminal y no aparece en las capturas.
- [completar] Quién revisó cada documento y en qué fecha.

## 6. Otros usos de IA en la unidad

[completar] Si se usó IA en otras partes (código de VetCare 24, unidades 2 y 3, otras herramientas), anotar aquí herramienta, fecha, para qué se usó y cómo se revisó.
