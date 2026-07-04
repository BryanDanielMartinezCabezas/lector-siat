import pytest

from src.captura.disparador import (Disparador, DisparadorManual,
                                     DisparadorSensorIR)
from src.captura.indicador_led import IndicadorLed, LedVirtual, LedHardware


def test_disparador_manual_invoca_callback():
    llamado = {"n": 0}
    disp = DisparadorManual()
    disp.armar(lambda: llamado.__setitem__("n", llamado["n"] + 1))
    disp.disparar()
    disp.disparar()
    assert llamado["n"] == 2


def test_disparador_manual_sin_armar_no_falla():
    DisparadorManual().disparar()  # no debe lanzar excepción


def test_disparador_es_subclase_de_abc():
    assert issubclass(DisparadorManual, Disparador)
    assert issubclass(DisparadorSensorIR, Disparador)


def test_sensor_ir_sin_hardware_lanza_al_armar():
    disp = DisparadorSensorIR(puerto="COM_INEXISTENTE")
    with pytest.raises(NotImplementedError):
        disp.armar(lambda: None)


def test_led_virtual_notifica_estado():
    estados = []
    led = LedVirtual(al_cambiar=estados.append)
    led.verde()
    led.rojo()
    assert estados == ["verde", "rojo"]


def test_led_es_subclase_de_abc():
    assert issubclass(LedVirtual, IndicadorLed)
    assert issubclass(LedHardware, IndicadorLed)


def test_led_hardware_sin_puerto_lanza():
    led = LedHardware(puerto="COM_INEXISTENTE")
    with pytest.raises(NotImplementedError):
        led.verde()
