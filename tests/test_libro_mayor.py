import json

import pytest

from src.extraccion.datos_fiscales import DatosFiscales
from src.libro_mayor.libro_mayor import LibroMayor


def _d():
    return DatosFiscales(
        nit="1020703023", numero_factura="104827",
        fecha="31/12/2026", importe="10.00", operadora="ENTEL",
    )


def test_agregar_y_leer(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    tx = lm.agregar(_d())
    assert tx == "TX-000001"
    assert lm.contadores()["pendiente"] == 1


def test_persistencia_y_reanudacion(tmp_path):
    ruta = str(tmp_path / "lm.json")
    lm = LibroMayor(ruta)
    lm.agregar(_d())
    lm.agregar(_d())
    lm.marcar("TX-000001", "completado")
    lm2 = LibroMayor(ruta)  # reabrir = reiniciar el sistema
    assert [t["id"] for t in lm2.pendientes()] == ["TX-000002"]


def test_estado_invalido_lanza(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    with pytest.raises(ValueError):
        lm.marcar("TX-000001", "volando")


def test_marcar_tx_inexistente_lanza(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    with pytest.raises(KeyError):
        lm.marcar("TX-999999", "completado")


def test_escritura_atomica_no_deja_tmp(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    assert list(tmp_path.glob("*.tmp")) == []
    json.loads((tmp_path / "lm.json").read_text(encoding="utf-8"))  # JSON válido


def test_siguiente_lote_de_cinco(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for _ in range(7):
        lm.agregar(_d())
    assert len(lm.siguiente_lote(5)) == 5


def test_agregar_guarda_ruta_de_imagen(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d(), imagen="datos/capturas/tarjeta_1.png")
    assert lm.todas()[0]["imagen"] == "datos/capturas/tarjeta_1.png"


def test_actualizar_datos_edicion_manual(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    lm.actualizar_datos("TX-000001", {"nit": "1020703023", "numero_factura": "999",
                                       "fecha": "01/01/2026", "importe": "20.00"})
    assert lm.todas()[0]["datos"]["numero_factura"] == "999"


def test_eliminar_transaccion(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d()); lm.agregar(_d())
    lm.eliminar("TX-000001")
    assert [t["id"] for t in lm.todas()] == ["TX-000002"]


def test_vaciar_libro(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d()); lm.agregar(_d())
    lm.vaciar()
    assert lm.todas() == []


def test_contadores_por_estado(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for _ in range(3):
        lm.agregar(_d())
    lm.marcar("TX-000001", "completado")
    lm.marcar("TX-000002", "saltado")
    c = lm.contadores()
    assert c["completado"] == 1 and c["saltado"] == 1 and c["pendiente"] == 1


def test_puede_cargar_solo_si_pendiente(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    assert lm.puede_cargar("TX-000001") is True
    lm.marcar("TX-000001", "completado")
    assert lm.puede_cargar("TX-000001") is False   # completado no se recarga


def test_marcar_varias_cambia_en_masa(tmp_path):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for _ in range(3):
        lm.agregar(_d())
    lm.marcar_varias(["TX-000001", "TX-000003"], "saltado")
    c = lm.contadores()
    assert c["saltado"] == 2 and c["pendiente"] == 1


def test_estado_viejo_exitoso_ya_no_es_valido(tmp_path):
    import pytest
    lm = LibroMayor(str(tmp_path / "lm.json"))
    lm.agregar(_d())
    with pytest.raises(ValueError):
        lm.marcar("TX-000001", "exitoso")
