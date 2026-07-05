"""Punto de entrada del Lector SIAT.

Uso:
  python -m src.main                # abre la GUI
  python -m src.main --demo IMG     # procesa una imagen por consola (sin GUI)
"""
import argparse
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cargar_config():
    with open(os.path.join(RAIZ, "config", "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _demo_consola(ruta_imagen):
    import cv2
    from src.extraccion.pipeline import PipelineExtraccion
    from src.extraccion.ocr_motor import OcrMotor

    config = _cargar_config()
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
    parser.add_argument("--demo", metavar="IMG",
                        help="Procesa una imagen por consola y termina (sin GUI)")
    args = parser.parse_args()

    if args.demo:
        _demo_consola(args.demo)
        return

    from src.gui.app import lanzar
    lanzar(_cargar_config())


if __name__ == "__main__":
    main()
