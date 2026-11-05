"""Servicio de seguimiento de vacunación (Etapa 9): próxima aplicación y refuerzo."""

from datetime import date

from vetcare24.domain.seguimiento_vacunacion import (
    EstadoDeSeguimiento,
    ServicioDeSeguimientoDeVacunacion,
)
from vetcare24.domain.vacunacion import EsquemaDeVacunacion, Vacunacion

SERVICIO = ServicioDeSeguimientoDeVacunacion()


def _v(vacunacion_id, vacuna, fecha):
    return Vacunacion(vacunacion_id=vacunacion_id, mascota_id="M1", vacuna=vacuna,
                      fecha_aplicacion=fecha)


def _esquemas(*esquemas):
    return {e.clave: e for e in esquemas}


def _e(vacuna, dias, refuerzo=False, validado=True):
    return EsquemaDeVacunacion(vacuna=vacuna, frecuencia_dias=dias,
                               requiere_refuerzo=refuerzo, validado=validado)


def test_calcula_la_proxima_aplicacion_con_la_frecuencia_del_esquema():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))],
                                _esquemas(_e("Rabia", 30)))
    assert s.estado is EstadoDeSeguimiento.CALCULADO
    assert (s.vacuna, s.ultima_aplicacion, s.proxima_aplicacion) == (
        "Rabia", date(2026, 10, 1), date(2026, 10, 31))
    assert s.es_refuerzo is False and s.motivos == ()


def test_identifica_si_la_siguiente_aplicacion_es_un_refuerzo():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))],
                                _esquemas(_e("Rabia", 21, refuerzo=True)))
    assert s.es_refuerzo is True and s.proxima_aplicacion == date(2026, 10, 22)


def test_usa_la_ultima_aplicacion_y_conserva_el_historial_intacto():
    historial = [_v("V3", "Rabia", date(2026, 9, 1)), _v("V1", "Rabia", date(2024, 9, 1)),
                 _v("V2", "Rabia", date(2025, 9, 1))]
    (s,) = SERVICIO.seguimiento(historial, _esquemas(_e("Rabia", 365)))
    assert s.ultima_aplicacion == date(2026, 9, 1)
    assert s.proxima_aplicacion == date(2027, 9, 1)
    assert [v.vacunacion_id for v in historial] == ["V3", "V1", "V2"]  # no se tocó


def test_si_hay_dos_el_mismo_dia_gana_el_id_mayor():
    historial = [_v("V2", "Rabia", date(2026, 10, 1)), _v("V9", "Rabia", date(2026, 10, 1))]
    (s,) = SERVICIO.seguimiento(historial, _esquemas(_e("Rabia", 30)))
    assert s.proxima_aplicacion == date(2026, 10, 31)


def test_un_seguimiento_por_tipo_de_vacuna_ordenado_por_nombre():
    historial = [_v("V1", "Rabia", date(2026, 10, 1)), _v("V2", "Parvo", date(2026, 10, 5))]
    resultado = SERVICIO.seguimiento(historial, _esquemas(_e("Rabia", 30), _e("Parvo", 10)))
    assert [s.vacuna for s in resultado] == ["Parvo", "Rabia"]
    assert [s.proxima_aplicacion for s in resultado] == [date(2026, 10, 15), date(2026, 10, 31)]


def test_el_nombre_de_la_vacuna_no_distingue_mayusculas_ni_espacios():
    historial = [_v("V1", "  rabia ", date(2026, 10, 1)), _v("V2", "RABIA", date(2026, 11, 1))]
    (s,) = SERVICIO.seguimiento(historial, _esquemas(_e("Rabia", 30)))
    assert s.ultima_aplicacion == date(2026, 11, 1) and s.estado is EstadoDeSeguimiento.CALCULADO


def test_sin_esquema_el_seguimiento_queda_pendiente_y_no_es_un_error():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))], {})
    assert s.estado is EstadoDeSeguimiento.PENDIENTE_DE_ESQUEMA
    assert s.proxima_aplicacion is None and s.es_refuerzo is None
    assert s.motivos == ("ESQUEMA_NO_DEFINIDO",)


def test_con_esquema_sin_validar_tampoco_se_calcula():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))],
                                _esquemas(_e("Rabia", 30, validado=False)))
    assert s.estado is EstadoDeSeguimiento.PENDIENTE_DE_ESQUEMA
    assert s.motivos == ("ESQUEMA_NO_VALIDADO",) and s.proxima_aplicacion is None


def test_sin_historial_no_hay_seguimiento():
    assert SERVICIO.seguimiento([], _esquemas(_e("Rabia", 30))) == []


def test_las_fechas_respetan_los_anios_bisiestos():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2028, 2, 28))], _esquemas(_e("Rabia", 1)))
    assert s.proxima_aplicacion == date(2028, 2, 29)


def test_vence_pronto_incluye_vencidas_y_el_limite():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))], _esquemas(_e("Rabia", 30)))
    # la próxima es el 31 de octubre
    assert SERVICIO.vence_pronto(s, date(2026, 10, 1), 30)        # justo en el límite
    assert not SERVICIO.vence_pronto(s, date(2026, 10, 1), 29)    # un día antes del límite
    assert SERVICIO.vence_pronto(s, date(2026, 12, 1), 0)         # ya vencida
    assert SERVICIO.vence_pronto(s, date(2026, 10, 31), 0)        # vence hoy


def test_lo_pendiente_nunca_vence():
    (s,) = SERVICIO.seguimiento([_v("V1", "Rabia", date(2026, 10, 1))], {})
    assert not SERVICIO.vence_pronto(s, date(2030, 1, 1), 10_000)
