"""Casos de uso de la aplicación (CU-01: registrar y gestionar citas).

Cada caso de uso sigue el mismo guion:
  1. Comprobar que el rol tenga permiso.
  2. Abrir una unidad de trabajo, cargar lo necesario y pedirle al dominio que actúe.
  3. Guardar los cambios Y los eventos en la misma transacción (commit).
  4. Publicar los eventos DESPUÉS del commit (D-14): si algo falla antes, no se avisa a nadie.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from vetcare24.application.comandos import (
    ModificarCita,
    RegistrarMascota,
    RegistrarPropietario,
    SolicitarCita,
)
from vetcare24.application.control_de_acceso import Permiso, Rol, exigir
from vetcare24.application.despachador import Despachador
from vetcare24.application.errores import NoEncontrado, YaExiste
from vetcare24.application.puertos import UnidadDeTrabajo
from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.ciclo_de_vida import CicloDeVidaDeCita
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.disponibilidad import Disponibilidad
from vetcare24.domain.eventos import EventoDeDominio
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.propietario import Propietario
from vetcare24.domain.reglas_cita import (
    CitaEnContexto,
    beneficio_de_referencia,
    puede_procesarse,
)
from vetcare24.domain.specification import Evaluacion

FabricaDeUnidades = Callable[[], UnidadDeTrabajo]


class ReglaEvaluable(StrEnum):
    """Reglas de elegibilidad que se pueden consultar sin cambiar nada (D-03, D-05)."""

    PROCESAMIENTO = "procesamiento"
    BENEFICIO = "beneficio"


def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:8].upper()}"


class ServicioDeRegistro:
    """Propietarios, mascotas y catálogo. Recepción opera en nombre del propietario (A-03)."""

    def __init__(self, fabrica: FabricaDeUnidades,
                 generar_id: Callable[[str], str] = nuevo_id) -> None:
        self._fabrica = fabrica
        self._generar_id = generar_id

    def registrar_propietario(self, rol: Rol, comando: RegistrarPropietario) -> Propietario:
        exigir(rol, Permiso.REGISTRAR_PROPIETARIO)
        propietario = Propietario(
            comando.propietario_id or self._generar_id("PROP"),
            comando.nombre, comando.activo, comando.preferente,
        )
        with self._fabrica() as uow:
            if uow.propietarios.obtener(propietario.propietario_id):
                raise YaExiste("propietario", propietario.propietario_id)
            uow.propietarios.agregar(propietario)
            uow.commit()
        return propietario

    def registrar_mascota(self, rol: Rol, comando: RegistrarMascota) -> Mascota:
        exigir(rol, Permiso.REGISTRAR_MASCOTA)
        mascota = Mascota(
            mascota_id=comando.mascota_id or self._generar_id("MASC"),
            propietario_id=comando.propietario_id, nombre=comando.nombre,
            especie=comando.especie, raza=comando.raza, sexo=comando.sexo,
            fecha_nacimiento=comando.fecha_nacimiento, peso_kg=comando.peso_kg,
            alergias=comando.alergias,
        )
        with self._fabrica() as uow:
            if uow.propietarios.obtener(mascota.propietario_id) is None:
                raise NoEncontrado("propietario", mascota.propietario_id)
            if uow.mascotas.obtener(mascota.mascota_id):
                raise YaExiste("mascota", mascota.mascota_id)
            uow.mascotas.agregar(mascota)
            uow.commit()
        return mascota

    def obtener_propietario(self, rol: Rol, propietario_id: str) -> Propietario:
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            propietario = uow.propietarios.obtener(propietario_id)
        if propietario is None:
            raise NoEncontrado("propietario", propietario_id)
        return propietario

    def obtener_mascota(self, rol: Rol, mascota_id: str) -> Mascota:
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            mascota = uow.mascotas.obtener(mascota_id)
        if mascota is None:
            raise NoEncontrado("mascota", mascota_id)
        return mascota

    def listar_servicios(self, rol: Rol) -> list[ServicioVeterinario]:
        exigir(rol, Permiso.CONSULTAR_CATALOGO)
        with self._fabrica() as uow:
            return list(uow.servicios.todos().values())


@dataclass(frozen=True)
class _Contexto:
    cita: Cita
    propietario: Propietario
    catalogo: dict[str, ServicioVeterinario]
    disponibilidad: Disponibilidad


class ServicioDeCitas:
    def __init__(
        self,
        fabrica: FabricaDeUnidades,
        despachador: Despachador,
        ciclo: CicloDeVidaDeCita | None = None,
        generar_id: Callable[[str], str] = nuevo_id,
    ) -> None:
        self._fabrica = fabrica
        self._despachador = despachador
        self._ciclo = ciclo or CicloDeVidaDeCita()
        self._generar_id = generar_id

    # --- ayudas -----------------------------------------------------------------------------

    @staticmethod
    def _lineas(servicios: Iterable[tuple[str, int]]) -> list[ServicioSolicitado]:
        return [ServicioSolicitado(servicio_id, cantidad) for servicio_id, cantidad in servicios]

    @staticmethod
    def _cargar(uow: UnidadDeTrabajo, cita_id: str) -> _Contexto:
        """Carga la cita y reconstruye la capacidad: catálogo menos lo que ya consumen las
        citas CONFIRMADA y REALIZADA (D-08). No hay un contador aparte que pueda desfasarse."""
        cita = uow.citas.obtener(cita_id)
        if cita is None:
            raise NoEncontrado("cita", cita_id)
        propietario = uow.propietarios.obtener(cita.propietario_id)
        if propietario is None:
            raise NoEncontrado("propietario", cita.propietario_id)
        catalogo = uow.servicios.todos()
        disponibilidad = Disponibilidad.desde_catalogo(catalogo)
        disponibilidad.reservar(uow.citas.demanda_ocupada())
        return _Contexto(cita, propietario, catalogo, disponibilidad)

    def _terminar(self, uow: UnidadDeTrabajo, cita: Cita) -> Cita:
        """Guarda la cita y sus eventos en una transacción y luego publica los eventos."""
        uow.citas.guardar(cita)
        eventos: tuple[EventoDeDominio, ...] = cita.extraer_eventos()
        for evento in eventos:
            uow.eventos.agregar(evento)
        uow.commit()
        self._despachador.publicar(eventos)
        return cita

    # --- casos de uso -----------------------------------------------------------------------

    def solicitar(self, rol: Rol, comando: SolicitarCita) -> Cita:
        exigir(rol, Permiso.SOLICITAR_CITA)
        with self._fabrica() as uow:
            propietario = uow.propietarios.obtener(comando.propietario_id)
            if propietario is None:
                raise NoEncontrado("propietario", comando.propietario_id)
            mascota = uow.mascotas.obtener(comando.mascota_id)
            if mascota is None:
                raise NoEncontrado("mascota", comando.mascota_id)
            cita = Cita.solicitar(
                cita_id=comando.cita_id or self._generar_id("CITA"),
                propietario=propietario, mascota=mascota,
                lineas=self._lineas(comando.servicios),
                fecha_solicitud=comando.fecha_solicitud, catalogo=uow.servicios.todos(),
                autorizada=comando.autorizada, promocion_activa=comando.promocion_activa,
                referencia=comando.referencia,
            )
            if uow.citas.obtener(cita.cita_id):
                raise YaExiste("cita", cita.cita_id)
            uow.citas.agregar(cita)
            uow.commit()
        return cita

    def confirmar(self, rol: Rol, cita_id: str) -> Cita:
        exigir(rol, Permiso.CONFIRMAR_CITA)
        with self._fabrica() as uow:
            c = self._cargar(uow, cita_id)
            self._ciclo.confirmar(c.cita, c.propietario, c.catalogo, c.disponibilidad)
            return self._terminar(uow, c.cita)

    def realizar(self, rol: Rol, cita_id: str) -> Cita:
        exigir(rol, Permiso.REALIZAR_CITA)
        with self._fabrica() as uow:
            c = self._cargar(uow, cita_id)
            self._ciclo.realizar(c.cita)
            return self._terminar(uow, c.cita)

    def cancelar(self, rol: Rol, cita_id: str) -> Cita:
        exigir(rol, Permiso.CANCELAR_CITA)
        with self._fabrica() as uow:
            c = self._cargar(uow, cita_id)
            self._ciclo.cancelar(c.cita, c.disponibilidad)
            return self._terminar(uow, c.cita)

    def modificar(self, rol: Rol, comando: ModificarCita) -> Cita:
        exigir(rol, Permiso.MODIFICAR_CITA)
        with self._fabrica() as uow:
            c = self._cargar(uow, comando.cita_id)
            self._ciclo.modificar(
                c.cita, self._lineas(comando.servicios), c.catalogo, c.disponibilidad)
            return self._terminar(uow, c.cita)

    def obtener(self, rol: Rol, cita_id: str) -> Cita:
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            cita = uow.citas.obtener(cita_id)
        if cita is None:
            raise NoEncontrado("cita", cita_id)
        return cita

    def listar(self, rol: Rol, *, estado: EstadoCita | None = None,
               propietario_id: str | None = None) -> list[Cita]:
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            return uow.citas.listar(estado=estado, propietario_id=propietario_id)

    def evaluar(self, rol: Rol, cita_id: str, regla: ReglaEvaluable) -> Evaluacion:
        """Responde si la cita cumple una regla, con los motivos. No modifica nada."""
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            c = self._cargar(uow, cita_id)
        contexto = CitaEnContexto(
            c.cita, c.propietario, c.catalogo, c.disponibilidad.como_mapa())
        especificacion = (
            puede_procesarse() if regla is ReglaEvaluable.PROCESAMIENTO
            else beneficio_de_referencia()
        )
        return especificacion.evaluar(contexto)

    def catalogo(self) -> dict[str, ServicioVeterinario]:
        """Catálogo para calcular los importes de una respuesta. No lleva permiso propio:
        solo se usa sobre citas que quien llama ya obtuvo (o modificó) con autorización, así
        una operación ya guardada nunca termina en un 403 al momento de responder."""
        with self._fabrica() as uow:
            return uow.servicios.todos()

    def listar_eventos(self, rol: Rol) -> list[dict[str, Any]]:
        exigir(rol, Permiso.CONSULTAR_CITA)
        with self._fabrica() as uow:
            return uow.eventos.todos()
