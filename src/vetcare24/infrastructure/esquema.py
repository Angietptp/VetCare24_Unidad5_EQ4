"""Esquema de la base de datos (tablas, llaves y restricciones).

Las restricciones CHECK y las llaves foráneas repiten en la base los invariantes del dominio:
si algún día se escribe por otra vía, la base también se niega a guardar datos imposibles.
Los importes se guardan en centavos (enteros) para no perder precisión; los booleanos, como 0/1.
"""

from __future__ import annotations

from vetcare24.infrastructure.base_de_datos import Conexion, Dialecto

TABLAS = (
    "propietarios", "mascotas", "servicios", "citas", "cita_lineas",
    "vacunaciones", "esquemas_vacunacion", "emergencias", "eventos_dominio",
)


def sentencias_de_creacion(dialecto: Dialecto) -> list[str]:
    return [
        """CREATE TABLE IF NOT EXISTS propietarios (
            propietario_id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            activo INTEGER NOT NULL CHECK (activo IN (0, 1)),
            preferente INTEGER NOT NULL CHECK (preferente IN (0, 1))
        )""",
        """CREATE TABLE IF NOT EXISTS mascotas (
            mascota_id TEXT PRIMARY KEY,
            propietario_id TEXT NOT NULL REFERENCES propietarios (propietario_id),
            nombre TEXT NOT NULL,
            especie TEXT NOT NULL,
            raza TEXT,
            sexo TEXT,
            fecha_nacimiento TEXT,
            peso_kg TEXT,
            alergias_json TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS servicios (
            servicio_id TEXT PRIMARY KEY,
            descripcion TEXT NOT NULL,
            precio_centavos BIGINT NOT NULL CHECK (precio_centavos >= 0),
            capacidad INTEGER NOT NULL CHECK (capacidad >= 0),
            habilitado INTEGER NOT NULL CHECK (habilitado IN (0, 1))
        )""",
        """CREATE TABLE IF NOT EXISTS citas (
            cita_id TEXT PRIMARY KEY,
            propietario_id TEXT NOT NULL REFERENCES propietarios (propietario_id),
            mascota_id TEXT NOT NULL REFERENCES mascotas (mascota_id),
            fecha_solicitud TEXT NOT NULL,
            estado TEXT NOT NULL
                CHECK (estado IN ('SOLICITADA', 'CONFIRMADA', 'REALIZADA', 'CANCELADA')),
            autorizada INTEGER NOT NULL CHECK (autorizada IN (0, 1)),
            promocion_activa INTEGER NOT NULL CHECK (promocion_activa IN (0, 1)),
            referencia TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS cita_lineas (
            cita_id TEXT NOT NULL REFERENCES citas (cita_id),
            posicion INTEGER NOT NULL,
            servicio_id TEXT NOT NULL REFERENCES servicios (servicio_id),
            cantidad INTEGER NOT NULL CHECK (cantidad >= 1),
            PRIMARY KEY (cita_id, posicion)
        )""",
        """CREATE TABLE IF NOT EXISTS vacunaciones (
            vacunacion_id TEXT PRIMARY KEY,
            mascota_id TEXT NOT NULL REFERENCES mascotas (mascota_id),
            vacuna TEXT NOT NULL,
            vacuna_clave TEXT NOT NULL,
            fecha_aplicacion TEXT NOT NULL,
            lote TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS esquemas_vacunacion (
            vacuna_clave TEXT PRIMARY KEY,
            vacuna TEXT NOT NULL,
            frecuencia_dias INTEGER NOT NULL CHECK (frecuencia_dias >= 1),
            requiere_refuerzo INTEGER NOT NULL CHECK (requiere_refuerzo IN (0, 1)),
            validado INTEGER NOT NULL CHECK (validado IN (0, 1))
        )""",
        """CREATE TABLE IF NOT EXISTS emergencias (
            emergencia_id TEXT PRIMARY KEY,
            mascota_id TEXT REFERENCES mascotas (mascota_id),
            motivo TEXT NOT NULL CHECK (motivo <> ''),
            datos_paciente TEXT,
            estado TEXT NOT NULL CHECK (estado IN ('IDENTIFICADA', 'EN_ATENCION')),
            identificada_en TEXT NOT NULL,
            atendida_en TEXT,
            CHECK ((estado = 'EN_ATENCION') = (atendida_en IS NOT NULL))
        )""",
        f"""CREATE TABLE IF NOT EXISTS eventos_dominio (
            secuencia {dialecto.llave_serie},
            evento TEXT NOT NULL,
            agregado_tipo TEXT NOT NULL,
            agregado_id TEXT NOT NULL,
            ocurrido_en TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_citas_estado ON citas (estado)",
        "CREATE INDEX IF NOT EXISTS idx_citas_propietario ON citas (propietario_id)",
        "CREATE INDEX IF NOT EXISTS idx_vacunaciones_mascota"
        " ON vacunaciones (mascota_id, vacuna_clave)",
        "CREATE INDEX IF NOT EXISTS idx_emergencias_mascota ON emergencias (mascota_id)",
        "CREATE INDEX IF NOT EXISTS idx_eventos_agregado"
        " ON eventos_dominio (agregado_tipo, agregado_id)",
    ]


class EsquemaDesactualizado(RuntimeError):
    """La base tiene tablas de una versión anterior del proyecto."""


def _es_la_tabla_anterior(conexion: Conexion) -> bool:
    """La versión anterior de `eventos_dominio` guardaba solo `cita_id`."""
    try:
        conexion.consultar("SELECT cita_id FROM eventos_dominio LIMIT 0")
    except Exception:
        conexion.rollback()
        return False
    return True


def crear_esquema(conexion: Conexion) -> None:
    """Crea las tablas que falten. Se puede ejecutar varias veces sin riesgo.

    No migra tablas existentes: si `eventos_dominio` es de la versión anterior, avisa con un
    mensaje claro en lugar de dejar un error de SQL difícil de entender.
    """
    try:
        for sentencia in sentencias_de_creacion(conexion.dialecto):
            conexion.ejecutar(sentencia)
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        if _es_la_tabla_anterior(conexion):
            raise EsquemaDesactualizado(
                "La tabla eventos_dominio es de una versión anterior (la Etapa 9 cambió "
                "cita_id por agregado_tipo y agregado_id). Reinicia la base de desarrollo con "
                "`docker compose down -v` y vuelve a cargar los datos."
            ) from error
        raise


def eliminar_esquema(conexion: Conexion) -> None:
    """Borra TODAS las tablas del proyecto (pruebas y reinicios).

    En PostgreSQL usa CASCADE: si la base tiene una tabla de otra versión que apunta a las del
    proyecto (p. ej. una etapa posterior), sus llaves foráneas no impiden el borrado (N-10).
    """
    cascada = " CASCADE" if conexion.dialecto.es_postgres else ""
    for tabla in reversed(TABLAS):
        conexion.ejecutar(f"DROP TABLE IF EXISTS {tabla}{cascada}")
    conexion.commit()
