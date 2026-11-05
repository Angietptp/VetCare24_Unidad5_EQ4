"""Pruebas del modelo de dominio (Etapa 3): invariantes de cada objeto."""

from datetime import date
from decimal import Decimal

import pytest

from vetcare24.domain.catalogo import ServicioVeterinario
from vetcare24.domain.cita import Cita, EstadoCita, ServicioSolicitado
from vetcare24.domain.errors import InvarianteViolada
from vetcare24.domain.mascota import Mascota
from vetcare24.domain.money import Money
from vetcare24.domain.propietario import Propietario

FECHA = date(2026, 10, 2)


def _catalogo():
    consulta = ServicioVeterinario("S1", "Consulta", Money.mxn("300"), capacidad=5)
    vacuna = ServicioVeterinario("S2", "Vacuna", Money.mxn("150.50"), capacidad=5)
    cerrado = ServicioVeterinario("S3", "Cerrado", Money.mxn("10"), capacidad=5, habilitado=False)
    return {s.servicio_id: s for s in (consulta, vacuna, cerrado)}


def _solicitar(lineas, propietario=None, mascota=None, catalogo=None, **extra):
    propietario = propietario or Propietario("P1", "Ana")
    mascota = mascota or Mascota(
        mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro"
    )
    return Cita.solicitar(
        cita_id="C1", propietario=propietario, mascota=mascota, lineas=lineas,
        fecha_solicitud=FECHA, catalogo=catalogo or _catalogo(), autorizada=True, **extra,
    )


def _codigo(funcion):
    with pytest.raises(InvarianteViolada) as error:
        funcion()
    return error.value.codigo


# --- ServicioVeterinario y Propietario ---

def test_servicio_valido_y_capacidad_cero_permitida():
    assert ServicioVeterinario("S", "Algo", Money.mxn("1"), capacidad=0).capacidad == 0


@pytest.mark.parametrize("capacidad", [-1, 1.5, True, "3"])
def test_servicio_rechaza_capacidad_invalida(capacidad):
    codigo = _codigo(lambda: ServicioVeterinario("S", "Algo", Money.mxn("1"), capacidad))
    assert codigo == "CAPACIDAD_INVALIDA"


def test_servicio_rechaza_id_vacio_y_precio_que_no_es_money():
    assert _codigo(lambda: ServicioVeterinario(" ", "Algo", Money.mxn("1"), 1)) == "ID_VACIO"
    with pytest.raises(TypeError):
        ServicioVeterinario("S", "Algo", 10, 1)


def test_servicio_rechaza_descripcion_vacia_y_habilitado_invalido():
    assert _codigo(lambda: ServicioVeterinario("S", "", Money.mxn("1"), 1)) == "DESCRIPCION_VACIA"
    assert _codigo(
        lambda: ServicioVeterinario("S", "Algo", Money.mxn("1"), 1, habilitado=1)
    ) == "HABILITADO_INVALIDO"


def test_propietario_valida_sus_campos():
    assert _codigo(lambda: Propietario("", "Ana")) == "ID_VACIO"
    assert _codigo(lambda: Propietario("P1", " ")) == "NOMBRE_VACIO"
    assert _codigo(lambda: Propietario("P1", "Ana", activo="si")) == "ACTIVO_INVALIDO"
    assert _codigo(lambda: Propietario("P1", "Ana", preferente=1)) == "PREFERENTE_INVALIDO"


# --- Mascota ---

def test_mascota_basica_con_peso_y_alergias():
    m = Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro",
                peso_kg="12.5", alergias=["Penicilina", "penicilina", "Polen"])
    assert m.peso_kg == Decimal("12.5")
    assert m.alergias == ("Penicilina", "Polen")


@pytest.mark.parametrize("peso", [0, -1, 1.5, "abc", "NaN", True])
def test_mascota_rechaza_peso_invalido(peso):
    with pytest.raises(InvarianteViolada) as error:
        Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro", peso_kg=peso)
    assert error.value.codigo == "PESO_INVALIDO"


def test_mascota_exige_datos_minimos():
    base = {"mascota_id": "M1", "propietario_id": "P1", "nombre": "Rex", "especie": "Perro"}
    for campo, codigo in [("mascota_id", "ID_VACIO"), ("propietario_id", "PROPIETARIO_REQUERIDO"),
                          ("nombre", "NOMBRE_VACIO"), ("especie", "ESPECIE_VACIA")]:
        datos = {**base, campo: ""}
        assert _codigo(lambda datos=datos: Mascota(**datos)) == codigo


def test_mascota_registra_peso_y_alergia_nuevos():
    m = Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro")
    assert m.peso_kg is None
    m.registrar_peso(Decimal("8.2"))
    m.registrar_alergia("Polen")
    assert (m.peso_kg, m.alergias) == (Decimal("8.2"), ("Polen",))
    assert _codigo(lambda: m.registrar_peso(0)) == "PESO_INVALIDO"
    assert m.peso_kg == Decimal("8.2")  # un peso inválido no cambia el estado
    assert _codigo(lambda: m.registrar_alergia(" ")) == "ALERGIA_VACIA"


def test_mascota_se_identifica_por_su_id():
    a = Mascota(mascota_id="M1", propietario_id="P1", nombre="Rex", especie="Perro")
    b = Mascota(mascota_id="M1", propietario_id="P1", nombre="Otro", especie="Gato")
    assert a == b and hash(a) == hash(b)
    assert "M1" in repr(a)
    assert a.raza is None and a.sexo is None and a.fecha_nacimiento is None


# --- ServicioSolicitado ---

@pytest.mark.parametrize("cantidad", [0, -2, 1.5, True, "2"])
def test_linea_rechaza_cantidad_invalida(cantidad):
    assert _codigo(lambda: ServicioSolicitado("S1", cantidad)) == "CANTIDAD_INVALIDA"


def test_linea_rechaza_servicio_vacio():
    assert _codigo(lambda: ServicioSolicitado("", 1)) == "ID_VACIO"


# --- Cita.solicitar (cita nueva: reglas de negocio) ---

def test_solicitar_crea_cita_solicitada():
    cita = _solicitar([ServicioSolicitado("S1", 2), ServicioSolicitado("S2", 1)])
    assert cita.estado is EstadoCita.SOLICITADA
    assert cita.propietario_id == "P1" and cita.mascota_id == "M1"
    assert cita.autorizada is True and cita.promocion_activa is False
    assert len(cita.lineas) == 2 and cita.fecha_solicitud == FECHA and cita.referencia is None


def test_solicitar_exige_al_menos_una_linea():
    assert _codigo(lambda: _solicitar([])) == "DETALLE_VACIO"


def test_solicitar_rechaza_servicio_deshabilitado_o_inexistente():
    assert _codigo(lambda: _solicitar([ServicioSolicitado("S3", 1)])) == "SERVICIO_DESHABILITADO"
    assert _codigo(lambda: _solicitar([ServicioSolicitado("S9", 1)])) == "SERVICIO_INEXISTENTE"


def test_solicitar_rechaza_mascota_de_otro_propietario():
    ajena = Mascota(mascota_id="M2", propietario_id="P2", nombre="Luna", especie="Gato")
    codigo = _codigo(lambda: _solicitar([ServicioSolicitado("S1", 1)], mascota=ajena))
    assert codigo == "MASCOTA_AJENA"


# --- Cita (reconstitución: estructura, no reglas de negocio) ---

def _reconstituir(**cambios):
    datos = {
        "cita_id": "C1", "propietario_id": "P1", "mascota_id": "M1",
        "lineas": [ServicioSolicitado("S1", 1)], "fecha_solicitud": FECHA,
        "estado": EstadoCita.SOLICITADA, "autorizada": True,
    }
    return Cita(**{**datos, **cambios})


def test_reconstituir_permite_historicos_que_hoy_se_rechazarian():
    assert _reconstituir(lineas=[]).lineas == ()
    assert _reconstituir(autorizada=False).autorizada is False
    assert _reconstituir(estado=EstadoCita.REALIZADA).estado is EstadoCita.REALIZADA


def test_reconstituir_valida_la_estructura():
    assert _codigo(lambda: _reconstituir(cita_id="")) == "ID_VACIO"
    assert _codigo(lambda: _reconstituir(propietario_id="")) == "PROPIETARIO_REQUERIDO"
    assert _codigo(lambda: _reconstituir(mascota_id="")) == "MASCOTA_REQUERIDA"
    assert _codigo(lambda: _reconstituir(fecha_solicitud="2026-10-02")) == "FECHA_INVALIDA"
    assert _codigo(lambda: _reconstituir(estado="SOLICITADA")) == "ESTADO_INVALIDO"
    assert _codigo(lambda: _reconstituir(autorizada=1)) == "AUTORIZADA_INVALIDA"
    assert _codigo(lambda: _reconstituir(promocion_activa=None)) == "PROMOCION_INVALIDA"
    with pytest.raises(TypeError):
        _reconstituir(lineas=[("S1", 1)])


def test_la_cita_expone_solo_lectura():
    cita = _reconstituir()
    with pytest.raises(AttributeError):
        cita.estado = EstadoCita.CANCELADA
    assert isinstance(cita.lineas, tuple)


# --- total y demanda ---

def test_total_suma_precio_por_cantidad_con_decimal():
    cita = _solicitar([ServicioSolicitado("S1", 2), ServicioSolicitado("S2", 3)])
    assert cita.total(_catalogo()) == Money.mxn("1051.50")  # 2x300 + 3x150.50


def test_total_de_cita_sin_lineas_es_cero():
    assert _reconstituir(lineas=[]).total(_catalogo()) == Money.cero()


def test_total_con_servicio_fuera_del_catalogo_falla():
    cita = _reconstituir(lineas=[ServicioSolicitado("S9", 1)])
    assert _codigo(lambda: cita.total(_catalogo())) == "SERVICIO_INEXISTENTE"


def test_demanda_suma_servicios_repetidos():
    cita = _reconstituir(lineas=[ServicioSolicitado("S1", 2), ServicioSolicitado("S1", 3)])
    assert cita.demanda_por_servicio() == {"S1": 5}


def test_la_cita_se_identifica_por_su_id():
    assert _reconstituir() == _reconstituir(autorizada=False)
    assert hash(_reconstituir()) == hash(_reconstituir())
    assert _reconstituir() != _reconstituir(cita_id="C2")
    assert "C1" in repr(_reconstituir()) and _reconstituir() != "C1"
