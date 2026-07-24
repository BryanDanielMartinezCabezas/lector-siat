from src.extraccion.datos_fiscales import DatosFiscales
from src.libro_mayor.libro_mayor import LibroMayor
from src.siat.lote import procesar_lote, ControlLote


class TecleadorFake:
    def seleccionar_todo(self): pass
    def borrar(self): pass
    def escribir(self, t): pass
    def tab(self): pass
    def pausa(self, s): pass


class LocalizadorFake:
    def __init__(self, fallar=None):
        self.fallar = fallar or set()
    def clic(self, ancla):
        return ancla not in self.fallar


def _libro(tmp_path, n):
    lm = LibroMayor(str(tmp_path / "lm.json"))
    for i in range(n):
        lm.agregar(DatosFiscales(nit="1020703023", numero_factura=str(100 + i),
                                 autorizacion="123189FFD1971B", fecha="01/07/2026",
                                 importe="10.00"))
    return lm


def test_procesa_todas_las_pendientes(tmp_path):
    lm = _libro(tmp_path, 3)
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(), ControlLote(),
                      pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 3 and r["pendiente"] == 0


def test_no_reprocesa_completadas(tmp_path):
    lm = _libro(tmp_path, 2)
    lm.marcar("TX-000001", "completado")
    procesar_lote(lm, TecleadorFake(), LocalizadorFake(), ControlLote(),
                  pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    # la ya completada sigue una sola vez; ambas quedan completado, ninguna duplicada
    assert lm.contadores()["completado"] == 2


def test_aborto_detiene_y_devuelve_actual_a_pendiente(tmp_path):
    lm = _libro(tmp_path, 3)
    control = ControlLote()
    # localizador que falla -> simula que no se pudo enviar la primera
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(fallar={"adicionar"}),
                      control, pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 0
    assert r["pendiente"] == 3   # la que se intentó volvió a pendiente


def test_abortar_por_control_corta_el_bucle(tmp_path):
    lm = _libro(tmp_path, 3)
    control = ControlLote(); control.abortar()
    r = procesar_lote(lm, TecleadorFake(), LocalizadorFake(), control,
                      pausa_campo=0, pausa_envio=0, dormir=lambda s: None)
    assert r["completado"] == 0 and r["pendiente"] == 3
