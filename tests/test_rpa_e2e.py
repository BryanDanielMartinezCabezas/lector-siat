import pytest

from src.extraccion.datos_fiscales import DatosFiscales
from src.libro_mayor.libro_mayor import LibroMayor
from src.siat.rpa_selenium import EjecutorRPA, Credenciales

pytestmark = pytest.mark.e2e

CRED = Credenciales(nit="123456789", email="a@b.c", password="x")


def _cargar(lm, cantidad):
    for i in range(cantidad):
        lm.agregar(DatosFiscales(
            nit="1020703023", numero_factura=str(100 + i),
            autorizacion="300400500600", fecha="31/12/2026", importe="10.00",
        ))


def test_procesa_todo_exitoso(mock_server, tmp_path, selectores):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    _cargar(lm, 6)  # 2 lotes de 5 -> relogueo entre lotes
    rpa = EjecutorRPA("mock", selectores, lm, CRED, headless=True)
    resumen = rpa.procesar_todo()
    assert resumen["exitoso"] == 6
    assert resumen["pendiente"] == 0


def test_error_detiene_todo_y_preserva_estado(mock_server_falla_tercera, tmp_path, selectores):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    _cargar(lm, 5)
    rpa = EjecutorRPA("mock", selectores, lm, CRED, headless=True)
    resumen = rpa.procesar_todo()
    assert resumen["exitoso"] == 2      # las dos primeras
    assert resumen["fallido"] == 1      # la tercera
    assert resumen["pendiente"] == 2    # 4ta y 5ta quedan intactas
