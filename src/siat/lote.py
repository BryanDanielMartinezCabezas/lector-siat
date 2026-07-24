"""Orquesta el bucle 'Cargar todos': recorre las tarjetas pendientes, las escribe
en el SIAT y las marca completado, respetando pausa/aborto y sin reprocesar las ya
completadas.
"""
import threading
import time

from .rellenador import (cargar_registro, cargar_y_enviar, enviar_y_reabrir,
                         SECUENCIA_RCV)


class ControlLote:
    def __init__(self):
        self._pausa = threading.Event()
        self._aborto = threading.Event()
        # Motivo por el que se detuvo el lote (None si terminó normal):
        #   "ancla_no_encontrada" | "error" | None
        self.motivo = None

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

    control.motivo = None
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
        try:
            cambiar(tx["id"], "en_proceso")
            cargar_registro(tx["datos"], tecleador, secuencia, pausa=pausa_campo)
            if enviar_y_reabrir(localizador, pausa=pausa_envio):
                cambiar(tx["id"], "completado")
            else:
                # No se pudo enviar: devolver a pendiente y cortar sin clicar a ciegas.
                cambiar(tx["id"], "pendiente")
                control.motivo = "ancla_no_encontrada"
                break
        except Exception:  # noqa: BLE001 - failsafe de pyautogui u otro fallo
            # No dejar la tarjeta colgada en "en_proceso": devolverla a pendiente
            # y cortar el bucle guardando el motivo (nunca tragar en silencio).
            cambiar(tx["id"], "pendiente")
            control.motivo = "error"
            break
    return libro.contadores()


def procesar_lote_teclado(libro, tecleador, control, secuencia=None,
                          pausa_campo=0.35, tabs_hasta_adicionar=16,
                          tecla_enviar="space", tabs_regreso=3, pausa_tras_envio=4.0,
                          al_cambiar=None, dormir=time.sleep) -> dict:
    """Bucle 100% teclado (Modo automático, sin calibración): por cada tarjeta
    pendiente llena los campos, la envía (Tabs hasta Adicionar + Espacio) y vuelve
    al campo NIT (`tabs_regreso` Tabs) para la siguiente. Se asume que el cursor
    arranca en el campo NIT. Respeta pausa/aborto y no reprocesa las completadas.
    """
    secuencia = secuencia or SECUENCIA_RCV

    def cambiar(tx_id, estado):
        libro.marcar(tx_id, estado)
        if al_cambiar:
            al_cambiar(tx_id, estado)

    control.motivo = None
    while True:
        pendientes = libro.pendientes()
        if not pendientes or control.esta_abortado():
            break
        tx = pendientes[0]
        while control.esta_pausado() and not control.esta_abortado():
            dormir(0.1)
        if control.esta_abortado():
            break
        try:
            cambiar(tx["id"], "en_proceso")
            cargar_y_enviar(tx["datos"], tecleador, secuencia, pausa_campo,
                            tabs_hasta_adicionar, tecla_enviar)
            cambiar(tx["id"], "completado")
            # Si quedan más pendientes, esperar a que el formulario se recargue
            # (depende del internet) ANTES de tabular de vuelta al NIT.
            if len(pendientes) > 1:
                dormir(pausa_tras_envio)
                for _ in range(tabs_regreso):
                    tecleador.tab()
                    tecleador.pausa(pausa_campo)
        except Exception:  # noqa: BLE001 - failsafe de pyautogui u otro fallo
            cambiar(tx["id"], "pendiente")
            control.motivo = "error"
            break
    return libro.contadores()
