from src.extraccion.datos_fiscales import DatosFiscales
from src.extraccion.validador import validar


def _datos_ok():
    return DatosFiscales(
        nit="1020703023", numero_factura="104827",
        autorizacion="300400500600", fecha="31/12/2026",
        importe="10.00", operadora="ENTEL",
    )


def test_datos_completos_sin_errores():
    assert validar(_datos_ok()) == []


def test_nit_corto_es_error():
    d = _datos_ok(); d.nit = "12345"
    assert any("NIT" in e for e in validar(d))


def test_nit_faltante_es_error():
    d = _datos_ok(); d.nit = None
    assert any("NIT" in e for e in validar(d))


def test_nit_desconocido_advierte_operadora():
    d = _datos_ok(); d.nit = "9999999999"; d.operadora = None
    assert any("operadora" in e.lower() for e in validar(d))


def test_fecha_invalida():
    d = _datos_ok(); d.fecha = "45/13/2026"
    assert any("fecha" in e.lower() for e in validar(d))


def test_importe_cero_o_negativo():
    d = _datos_ok(); d.importe = "0"
    assert any("importe" in e.lower() for e in validar(d))


def test_importe_no_numerico():
    d = _datos_ok(); d.importe = "diez"
    assert any("importe" in e.lower() for e in validar(d))
