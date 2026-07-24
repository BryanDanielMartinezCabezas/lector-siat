"""Orquesta el bucle 'Cargar todos': recorre las tarjetas pendientes, las escribe
en el SIAT y las marca completado, respetando pausa/aborto y sin reprocesar las ya
completadas.
"""
import threading
import time

from .rellenador import cargar_registro, enviar_y_reabrir, SECUENCIA_RCV


class ControlLote:
    def __init__(self):
        self._pausa = threading.Event()
        self._aborto = threading.Event()

    def pausar(self): self._pausa.set()
    def reanudar(self): self._pausa.clear()
    def abortar(self): self._aborto.set()
    def esta_pausado(self) -> bool: return self._pausa.is_set()
    def esta_abortado(self) -> bool: return self._aborto.is_set()


def procesar_lote(libro, tecleador, localizador, control, secuencia=None,
                  pausa_campo=0.35, pausa_envio=0.6, al_cambiar=None,
                  dormir=time.sleep) -> dict:
    secuencia = secuencia or SECUENCIA_RCV

    def cambiar(tx_id, estado):
        libro.marcar(tx_id, estado)
        if al_cambiar:
            al_cambiar(tx_id, estado)

    while True:
        pendientes = libro.pendientes()
        if not pendientes or control.esta_abortado():
            break
        tx = pendientes[0]
        # Esperar mientras esté en pausa (nunca a mitad de una tarjeta).
        while control.esta_pausado() and not control.esta_abortado():
            dormir(0.1)
        if control.esta_abortado():
            break
        cambiar(tx["id"], "en_proceso")
        cargar_registro(tx["datos"], tecleador, secuencia, pausa=pausa_campo)
        if enviar_y_reabrir(localizador, pausa=pausa_envio):
            cambiar(tx["id"], "completado")
        else:
            # No se pudo enviar: devolver a pendiente y cortar sin clicar a ciegas.
            cambiar(tx["id"], "pendiente")
            break
    return libro.contadores()
