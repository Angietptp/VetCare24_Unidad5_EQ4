"""Recorrido por HTTP de CU-05 (Etapa 10): 20 escenarios en orden, con su resultado esperado.

Los escenarios comparten la base (cada uno parte de lo que dejó el anterior). Se usan en
`tests/test_api_emergencias.py` (deben coincidir todos) y en
`python -m tests.evidencia_emergencias`, que los guarda en un CSV como evidencia.

Resultados esperados derivados de NB-19, R-06, US20, A-01 y las decisiones N-01 a N-10: ni el
paquete del profesor ni el BRD traen datos de emergencias, así que no hay oráculo oficial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from vetcare24.domain.mascota import Mascota
from vetcare24.infrastructure.repositorios_sql import UnidadDeTrabajoSql

RECEPCION, VET = "recepcion", "veterinario"
CLINICO, RESPONSABLE = "personal_clinico", "responsable"


@dataclass(frozen=True)
class Escenario:
    id: str
    descripcion: str
    rol: str | None
    metodo: str
    ruta: str
    cuerpo: dict[str, Any] | None
    http_esperado: int
    resultado_esperado: str  # error.codigo si falla; lo verificado si tiene éxito
    regla: str


ESCENARIOS = (
    Escenario("E01", "Recepción registra una emergencia de M1, que NO tiene cita", RECEPCION,
              "POST", "/emergencias",
              {"motivo": "Atropellamiento", "mascota_id": "M1", "emergencia_id": "EMER-E01"},
              201, "IDENTIFICADA · protocolo · notificado", "NB-19, R-06, A-01"),
    Escenario("E02", "Recepción registra una emergencia sin mascota registrada", RECEPCION,
              "POST", "/emergencias",
              {"motivo": "Intoxicación", "datos_paciente": "Gato atigrado, lo trae un vecino",
               "emergencia_id": "EMER-E02"},
              201, "IDENTIFICADA · protocolo · notificado", "P3"),
    Escenario("E03", "El veterinario no registra emergencias", VET, "POST", "/emergencias",
              {"motivo": "x"}, 403, "ACCESO_DENEGADO", "A-01, N-07"),
    Escenario("E04", "El personal clínico no registra emergencias", CLINICO, "POST",
              "/emergencias", {"motivo": "x"}, 403, "ACCESO_DENEGADO", "A-01, N-07"),
    Escenario("E05", "Sin encabezado X-Rol", None, "POST", "/emergencias", {"motivo": "x"},
              401, "ROL_REQUERIDO", "K-02"),
    Escenario("E06", "Mascota indicada que no existe", RECEPCION, "POST", "/emergencias",
              {"motivo": "x", "mascota_id": "NO-EXISTE"}, 404, "NO_ENCONTRADO", "D-13"),
    Escenario("E07", "Motivo en blanco", RECEPCION, "POST", "/emergencias", {"motivo": "  "},
              422, "MOTIVO_VACIO", "N-04"),
    Escenario("E08", "Falta el campo motivo", RECEPCION, "POST", "/emergencias",
              {"mascota_id": "M1"}, 400, "SOLICITUD_INVALIDA", "K-03"),
    Escenario("E09", "Identificador repetido", RECEPCION, "POST", "/emergencias",
              {"motivo": "x", "emergencia_id": "EMER-E01"}, 409, "YA_EXISTE", "K-03"),
    Escenario("E10", "El veterinario recibió los dos avisos", VET, "GET", "/avisos-veterinario",
              None, 200, "2 aviso(s)", "NB-19, CR-8, N-08"),
    Escenario("E11", "M1 puede recibir atención sin cita (es emergencia)", VET, "GET",
              "/mascotas/M1/evaluaciones/atencion", None, 200, "cumple", "R-06, N-09"),
    Escenario("E12", "M2 no tiene cita confirmada ni emergencia", VET, "GET",
              "/mascotas/M2/evaluaciones/atencion", None, 200,
              "no cumple: SIN_CITA_CONFIRMADA|SIN_EMERGENCIA_ACTIVA", "R-06, N-09"),
    Escenario("E13", "Recepción no inicia la atención", RECEPCION, "POST",
              "/emergencias/EMER-E01/iniciar-atencion", None, 403, "ACCESO_DENEGADO",
              "A-01, N-07"),
    Escenario("E14", "El personal clínico inicia la atención", CLINICO, "POST",
              "/emergencias/EMER-E01/iniciar-atencion", None, 200, "EN_ATENCION",
              "US20, N-02"),
    Escenario("E15", "Iniciar otra vez la misma atención", CLINICO, "POST",
              "/emergencias/EMER-E01/iniciar-atencion", None, 409, "TRANSICION_INVALIDA",
              "N-02, D-12"),
    Escenario("E16", "Iniciar la atención de una que no existe", CLINICO, "POST",
              "/emergencias/EMER-NO/iniciar-atencion", None, 404, "NO_ENCONTRADO", "D-13"),
    Escenario("E17", "El responsable consulta la emergencia", RESPONSABLE, "GET",
              "/emergencias/EMER-E01", None, 200, "EN_ATENCION", "N-07"),
    Escenario("E18", "Listar las que esperan atención", CLINICO, "GET",
              "/emergencias?estado=IDENTIFICADA", None, 200, "1 resultado(s)", "N-02"),
    Escenario("E19", "Filtro con un estado que no existe", CLINICO, "GET",
              "/emergencias?estado=CERRADA", None, 400, "SOLICITUD_INVALIDA", "K-03"),
    Escenario("E20", "Los eventos EmergenciaIdentificada quedaron guardados", VET, "GET",
              "/eventos", None, 200, "2 EmergenciaIdentificada", "D-14, N-06"),
)


@dataclass(frozen=True)
class Resultado:
    escenario: Escenario
    http_obtenido: int
    resultado_obtenido: str

    @property
    def coincide(self) -> bool:
        e = self.escenario
        return (self.http_obtenido, self.resultado_obtenido) == (
            e.http_esperado, e.resultado_esperado)


def sembrar_mascotas(url: str) -> None:
    """Agrega la mascota M2 (P1) a la base de `tests.bd.sembrar_basico`."""
    with UnidadDeTrabajoSql(url) as uow:
        uow.mascotas.agregar(
            Mascota(mascota_id="M2", propietario_id="P1", nombre="Max", especie="Gato"))
        uow.commit()


def _resumir(escenario: Escenario, cuerpo: Any, status: int) -> str:
    if status >= 400:
        return cuerpo["error"]["codigo"]
    if escenario.ruta == "/eventos":
        n = sum(1 for e in cuerpo if e["evento"] == "EmergenciaIdentificada")
        return f"{n} EmergenciaIdentificada"
    if escenario.ruta == "/avisos-veterinario":
        return f"{len(cuerpo)} aviso(s)"
    if isinstance(cuerpo, list):
        return f"{len(cuerpo)} resultado(s)"
    if "cumple" in cuerpo:
        return "cumple" if cuerpo["cumple"] else "no cumple: " + "|".join(cuerpo["motivos"])
    if "emergencia" in cuerpo:
        protocolo = "protocolo" if cuerpo["protocolo_activado"] else "sin protocolo"
        return f"{cuerpo['emergencia']['estado']} · {protocolo} · {cuerpo['notificacion']}"
    return cuerpo["estado"]


def ejecutar(cliente: TestClient) -> list[Resultado]:
    resultados = []
    for e in ESCENARIOS:
        encabezados = {"X-Rol": e.rol} if e.rol else {}
        respuesta = cliente.request(e.metodo, e.ruta, json=e.cuerpo, headers=encabezados)
        resultados.append(Resultado(
            e, respuesta.status_code, _resumir(e, respuesta.json(), respuesta.status_code)))
    return resultados
