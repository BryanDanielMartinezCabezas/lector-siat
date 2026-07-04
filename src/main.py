"""Punto de entrada del Lector SIAT.

Uso:
  python -m src.main                # abre la GUI (perfil de config/config.json)
  python -m src.main --mock         # levanta el mock del SIAT y abre la GUI
  python -m src.main --demo IMG     # procesa una imagen por consola (sin GUI)
"""
import argparse
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cargar_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _cargar_config():
    config = _cargar_json(os.path.join(RAIZ, "config", "config.json"))
    selectores = _cargar_json(os.path.join(RAIZ, "config", "selectores_siat.json"))
    credenciales = {}
    ruta_cred = os.path.join(RAIZ, config.get("ruta_credenciales", ""))
    if config.get("ruta_credenciales") and os.path.exists(ruta_cred):
        credenciales = _cargar_json(ruta_cred)
    return config, selectores, credenciales


def _demo_consola(ruta_imagen):
    import cv2
    from src.extraccion.pipeline import PipelineExtraccion
    from src.extraccion.ocr_motor import OcrMotor

    config, _, _ = _cargar_config()
    imagen = cv2.imread(ruta_imagen)
    if imagen is None:
        print(f"No se pudo abrir la imagen: {ruta_imagen}")
        return
    pipeline = PipelineExtraccion(
        ocr_motor=OcrMotor(os.path.join(RAIZ, config["ruta_modelos_ocr"])))
    r = pipeline.procesar_imagen(imagen)
    print(f"Método: {r.metodo}")
    print(f"Datos:  {r.datos.a_dict()}")
    print(f"Válido: {r.es_valido}  Errores: {r.errores}")


def main():
    parser = argparse.ArgumentParser(description="Lector SIAT — tarjetas prepago")
    parser.add_argument("--mock", action="store_true",
                        help="Levanta el mock del SIAT (puerto 5001) antes de la GUI")
    parser.add_argument("--demo", metavar="IMG",
                        help="Procesa una imagen por consola y termina (sin GUI)")
    args = parser.parse_args()

    if args.demo:
        _demo_consola(args.demo)
        return

    proceso_mock = None
    if args.mock:
        proceso_mock = subprocess.Popen(
            [sys.executable, "-m", "mock_siat.servidor"], cwd=RAIZ)
        time.sleep(2)
        print("Mock del SIAT en http://127.0.0.1:5001")

    try:
        from src.gui.app import lanzar
        config, selectores, credenciales = _cargar_config()
        lanzar(config, selectores, credenciales)
    finally:
        if proceso_mock is not None:
            proceso_mock.terminate()


if __name__ == "__main__":
    main()
