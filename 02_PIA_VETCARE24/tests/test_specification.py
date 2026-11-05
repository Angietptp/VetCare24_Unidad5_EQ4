"""Pruebas del patrón Specification con reglas de juguete sobre números (Etapa 4)."""

import pytest

from vetcare24.domain.specification import And, Evaluacion, Not, Or, Specification


class EsPar(Specification[int]):
    codigo = "NO_ES_PAR"

    def es_satisfecha_por(self, n: int) -> bool:
        return n % 2 == 0


class MayorQue(Specification[int]):
    def __init__(self, limite: int) -> None:
        self.limite = limite
        self.codigo = f"NO_MAYOR_QUE_{limite}"

    def es_satisfecha_por(self, n: int) -> bool:
        return n > self.limite

    def descripcion(self) -> str:
        return f"MayorQue({self.limite})"


class SinCodigo(Specification[int]):
    def es_satisfecha_por(self, n: int) -> bool:
        return False


def test_atomica_responde_y_explica():
    assert EsPar().es_satisfecha_por(4)
    assert EsPar().evaluar(4) == Evaluacion(True, ())
    assert EsPar().evaluar(3) == Evaluacion(False, ("NO_ES_PAR",))


def test_sin_codigo_usa_el_nombre_de_la_clase():
    assert SinCodigo().evaluar(1).motivos == ("SinCodigo",)


@pytest.mark.parametrize("n, esperado", [(12, True), (11, False), (4, False), (3, False)])
def test_and_exige_todas(n, esperado):
    assert (EsPar() & MayorQue(10)).es_satisfecha_por(n) is esperado


@pytest.mark.parametrize("n, esperado", [(12, True), (11, True), (4, True), (3, False)])
def test_or_exige_al_menos_una(n, esperado):
    assert (EsPar() | MayorQue(10)).es_satisfecha_por(n) is esperado


def test_not_invierte():
    assert (~EsPar()).es_satisfecha_por(3)
    assert not (~EsPar()).es_satisfecha_por(4)


def test_composicion_con_precedencia_de_python():
    regla = EsPar() | MayorQue(10) & ~EsPar()  # & se evalúa antes que |
    assert regla.es_satisfecha_por(2)
    assert regla.es_satisfecha_por(11)
    assert not regla.es_satisfecha_por(3)


def test_and_informa_solo_las_que_fallan():
    assert (EsPar() & MayorQue(10)).evaluar(3).motivos == ("NO_ES_PAR", "NO_MAYOR_QUE_10")
    assert (EsPar() & MayorQue(10)).evaluar(4).motivos == ("NO_MAYOR_QUE_10",)


def test_or_informa_todas_cuando_ninguna_se_cumple():
    assert (EsPar() | MayorQue(10)).evaluar(3).motivos == ("NO_ES_PAR", "NO_MAYOR_QUE_10")
    assert (EsPar() | MayorQue(10)).evaluar(4).cumple


def test_not_informa_su_codigo_o_uno_derivado():
    assert Not(EsPar(), "ES_PAR").evaluar(4).motivos == ("ES_PAR",)
    assert (~EsPar()).evaluar(4).motivos == ("NO_EsPar",)


def test_and_y_or_se_aplanan_y_conservan_el_orden():
    regla = (EsPar() & MayorQue(1)) & MayorQue(2)
    assert isinstance(regla, And) and len(regla.specs) == 3
    assert [type(s).__name__ for s in (EsPar() | MayorQue(1) | MayorQue(2)).specs] == [
        "EsPar", "MayorQue", "MayorQue"]


def test_motivos_sin_repetidos():
    regla = MayorQue(10) & MayorQue(10)
    assert regla.evaluar(1).motivos == ("NO_MAYOR_QUE_10",)


def test_descripcion_legible_con_parentesis_en_lo_anidado():
    regla = EsPar() & (MayorQue(10) | ~EsPar())
    assert regla.descripcion() == "EsPar AND (MayorQue(10) OR NOT EsPar)"
    assert str(regla) == regla.descripcion()
    assert (~(EsPar() | MayorQue(1))).descripcion() == "NOT (EsPar OR MayorQue(1))"


def test_and_y_or_exigen_al_menos_dos():
    with pytest.raises(ValueError):
        And(EsPar())
    with pytest.raises(ValueError):
        Or(EsPar())


def test_specification_es_abstracta():
    with pytest.raises(TypeError):
        Specification()
