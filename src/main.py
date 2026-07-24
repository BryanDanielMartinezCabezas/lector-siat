"""Punto de entrada del Lector SIAT.

Uso:
  python -m src.main                # abre la GUI
  python -m src.main --demo IMG     # procesa una imagen por consola (sin GUI)
"""
import argparse
import json
import os
import sys

# Cuando la app está empaquetada con PyInstaller los recursos (modelos_ocr,
# config, ...) se extraen a sys._MEIPASS. En modo desarrollo la raíz es el
# directorio que contiene la carpeta src/.
if getattr(sys, "frozen", False):
    RAIZ = sys._MEIPASS
    # Directorio donde vive el .exe (para guardar datos del usuario).
    RAIZ_EXE = os.path.dirname(sys.executable)
else:
    RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RAIZ_EXE = RAIZ


def _cargar_config():
    with open(os.path.join(RAIZ, "config", "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _resolver_rutas(config: dict) -> dict:
    """Convierte las rutas relativas del config en absolutas.

    - Recursos empaquetados (modelos_ocr)  →  RAIZ (sys._MEIPASS en frozen)
    - Datos del usuario (libro_mayor, capturas) →  RAIZ_EXE (directorio del .exe)
    - Credenciales                          →  RAIZ (dentro del paquete)
    """
    # Recursos incluidos en el paquete
    for clave in ("ruta_modelos_ocr", "ruta_credenciales"):
        if clave in config and not os.path.isabs(config[clave]):
            config[clave] = os.path.join(RAIZ, config[clave])

    # Datos del usuario (deben vivir junto al ejecutable, no en el paquete)
    for clave in ("ruta_libro_mayor", "ruta_capturas"):
        if clave in config and not os.path.isabs(config[clave]):
            config[clave] = os.path.join(RAIZ_EXE, config[clave])

    return config


def _demo_consola(ruta_imagen):
    import cv2
    from src.extraccion.pipeline import PipelineExtraccion
    from src.extraccion.ocr_motor import OcrMotor

    config = _resolver_rutas(_cargar_config())
    imagen = cv2.imread(ruta_imagen)
    if imagen is None:
        print(f"No se pudo abrir la imagen: {ruta_imagen}")
        return
    pipeline = PipelineExtraccion(
        ocr_motor=OcrMotor(config["ruta_modelos_ocr"]))
    r = pipeline.procesar_imagen(imagen)
    print(f"Método: {r.metodo}")
    print(f"Datos:  {r.datos.a_dict()}")
    print(f"Válido: {r.es_valido}  Errores: {r.errores}")


def main():
    parser = argparse.ArgumentParser(description="Lector SIAT — tarjetas prepago")
    parser.add_argument("--demo", metavar="IMG",
                        help="Procesa una imagen por consola y termina (sin GUI)")
    args = parser.parse_args()

    if args.demo:
        _demo_consola(args.demo)
        return

    from src.gui.app import lanzar
    lanzar(_resolver_rutas(_cargar_config()))


if __name__ == "__main__":
    main()
