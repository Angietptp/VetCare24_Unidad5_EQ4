"""Pruebas del importador de CSV (Etapa 2)."""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from vetcare24.infrastructure.config import load_settings
from vetcare24.infrastructure.csv_loader import ErrorDeDatos, cargar_paquete


def _copiar_datos(destino: Path) -> Path:
    for archivo in load_settings().data_dir.glob("*.csv"):
        shutil.copy(archivo, destino / archivo.name)
    return destino


def _reemplazar(directorio: Path, archivo: str, viejo: str, nuevo: str) -> None:
    ruta = directorio / archivo
    texto = ruta.read_text(encoding="utf-8-sig")
    assert viejo in texto, f"{viejo!r} no está en {archivo}"
    ruta.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8-sig")


def test_cuenta_registros_del_paquete():
    p = cargar_paquete(load_settings().data_dir)
    assert len(p.actores) == 40
    assert len(p.recursos) == 20
    assert len(p.operaciones) == 60
    assert p.total_lineas == 117
    assert len(p.casos) == 120
    assert len(p.transiciones) == 20


def test_importes_son_decimal_con_dos_decimales():
    p = cargar_paquete(load_settings().data_dir)
    assert all(isinstance(r.precio_mxn, Decimal) for r in p.recursos.values())
    assert p.recursos["VET-P001"].precio_mxn == Decimal("313.00")
    assert p.recursos["VET-P001"].precio_mxn.as_tuple().exponent == -2


def test_bom_no_contamina_las_llaves():
    p = cargar_paquete(load_settings().data_dir)
    assert "VET-C001" in p.actores
    assert p.actores["VET-C001"].ciudad == "Monterrey"


def test_conserva_registros_que_las_reglas_rechazaran():
    """D-09: el importador no filtra tutores inactivos, operaciones sin detalle, etc."""
    p = cargar_paquete(load_settings().data_dir)
    assert any(not a.activo for a in p.actores.values())
    assert any(not r.habilitado for r in p.recursos.values())
    assert any(not p.lineas_de(op_id) for op_id in p.operaciones)
    assert any(not o.autorizado for o in p.operaciones.values())


def test_archivo_faltante(tmp_path):
    with pytest.raises(ErrorDeDatos, match="Falta el archivo"):
        cargar_paquete(tmp_path)


def test_encabezado_distinto(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "actores.csv", "es_preferente", "vip")
    with pytest.raises(ErrorDeDatos, match="columnas"):
        cargar_paquete(tmp_path)


def test_booleano_invalido(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "actores.csv", "VET-C001,Tutor 01,0,1", "VET-C001,Tutor 01,2,1")
    with pytest.raises(ErrorDeDatos, match="0 o 1"):
        cargar_paquete(tmp_path)


def test_importe_invalido(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "catalogo.csv", "313.00", "abc")
    with pytest.raises(ErrorDeDatos, match="importe inválido"):
        cargar_paquete(tmp_path)


def test_entero_invalido(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "detalle_operaciones.csv", "VET-O001,VET-P009,3", "VET-O001,VET-P009,x")
    with pytest.raises(ErrorDeDatos, match="entero inválido"):
        cargar_paquete(tmp_path)


def test_fecha_invalida(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "operaciones.csv", "2026-10-02", "02/10/2026")
    with pytest.raises(ErrorDeDatos, match="fecha ISO"):
        cargar_paquete(tmp_path)


def test_clave_foranea_rota_en_detalle(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "detalle_operaciones.csv", "VET-O001,VET-P009", "VET-O001,VET-P999")
    with pytest.raises(ErrorDeDatos, match="recurso inexistente"):
        cargar_paquete(tmp_path)


def test_actor_inexistente_en_operacion(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "operaciones.csv", "VET-O001,VET-C012", "VET-O001,VET-C999")
    with pytest.raises(ErrorDeDatos, match="actor inexistente"):
        cargar_paquete(tmp_path)


def test_id_repetido(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "actores.csv", "VET-C002,Tutor 02", "VET-C001,Tutor 02")
    with pytest.raises(ErrorDeDatos, match="repetidos"):
        cargar_paquete(tmp_path)


def test_transicion_con_estado_inconsistente(tmp_path):
    _copiar_datos(tmp_path)
    _reemplazar(tmp_path, "transiciones_prueba.csv", "completar,SOLICITADA", "completar,CONFIRMADA")
    with pytest.raises(ErrorDeDatos, match="parte de"):
        cargar_paquete(tmp_path)
