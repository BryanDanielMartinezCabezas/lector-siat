# Lector SIAT — Software de la cajita lectora de tarjetas prepago

Software del proyecto de Robótica II (COM480, USFX): lee el reverso de las
tarjetas prepago de **Entel, Tigo y Viva**, extrae los datos fiscales y los
registra en el **Registro de Compras (RCV) del SIAT**. Parte de software del
sistema (la cajita física —cámara, sensor IR, LEDs— es la parte de hardware).

## Qué hace

1. **Captura** el reverso de la tarjeta con cámara USB (OpenCV).
2. **Extrae** los datos: primero decodifica el **QR** (pyzbar); si falla, usa
   **OCR** (PaddleOCR) + un extractor de campos calibrado para tarjetas bolivianas.
3. **Valida** NIT, número de factura, fecha e importe.
4. **Registra** cada factura en un **Libro Mayor** (JSON) con estados
   (`pendiente → en_proceso → exitoso | fallido | saltado`) y escritura atómica.
5. **Envía al SIAT** por dos vías:
   - **RPA (Selenium)**: llena el formulario factura por factura, en lotes de 5,
     con esperas explícitas, relogueo entre lotes y **detención total ante el
     primer fallo** preservando el progreso (reanuda donde quedó).
   - **Excel de importación masiva** del RCV (vía de respaldo, más robusta).

## Requisitos e instalación

```bash
py -3.11 -m venv .venv
.venv/Scripts/activate            # Windows
pip install -r requirements.txt
```

> Se usa Python 3.11 y `paddlepaddle==2.6.2` + `numpy==1.26.4` a propósito:
> paddle 3.x falla con oneDNN (`fused_conv2d`) en CPU, y paddleocr 2.7.3 necesita numpy 1.x.

## Cómo ejecutar

```bash
# GUI + mock del SIAT (demo completa con un solo comando)
python -m src.main --mock

# Solo la GUI (usa el perfil de config/config.json)
python -m src.main

# Procesar una imagen por consola (sin GUI), útil para probar el extractor
python -m src.main --demo ruta/a/tarjeta.png

# Levantar solo el mock del SIAT
python -m mock_siat.servidor      # http://127.0.0.1:5001
```

## Cómo correr las pruebas

```bash
pytest -q                         # todo (unitarias + OCR)
pytest -q -m e2e                  # solo E2E del RPA contra el mock (requiere Chrome)
pytest -q -m "not e2e and not ocr"# rápido, sin navegador ni OCR
```

## Estructura

```
config/            config.json + selectores_siat.json (perfiles mock/real) + credenciales.local.json (git-ignored)
modelos_ocr/       modelos PaddleOCR v4 (offline)
referencia_siat/   capturas del portal real (fidelidad del mock)
mock_siat/         réplica local fiel del portal SIAT (Flask)
src/
  captura/         camara.py, disparador.py, indicador_led.py (desacoplados del hardware)
  extraccion/      qr_lector, ocr_motor, extractor_fiscal, validador, pipeline
  libro_mayor/     libro_mayor.py (estados + escritura atómica)
  siat/            rpa_selenium.py, excel_rcv.py
  gui/             app.py (PyQt6), hilo_rpa.py
  main.py
tests/             pytest (extractor, validador, qr, ocr, libro mayor, excel, mock, rpa e2e, pipeline, disparador)
```

## Principio de diseño: acoplarse a la página del SIAT

El mock replica el HTML/CSS y los **ids reales** del portal (capturados con
Playwright, ver `referencia_siat/`). Los selectores viven en
`config/selectores_siat.json` con dos perfiles: `mock` y `real`. Pasar del mock
al portal real es cambiar `perfil_siat` en `config/config.json` y completar los
selectores del perfil `real` — sin tocar el código.

## Pasos para el dry-run contra el SIAT real

1. Iniciar sesión manualmente en https://siat.impuestos.gob.bo/ y abrir el
   formulario de **Registro de Compras** del RCV.
2. Con las herramientas del navegador (F12), copiar los `id`/selectores reales de
   cada campo y pegarlos en el perfil `real` de `config/selectores_siat.json`
   (mismas claves que el perfil `mock`), y poner la URL real en `url_registro_compra`.
3. Contrastar las columnas de `src/siat/excel_rcv.py` con el formato descargable
   vigente del RCV.
4. Cambiar `perfil_siat` a `"real"` en `config/config.json`.

> ⚠️ **Anti-automatización:** el portal real detecta el control por navegador
> (`--disable-blink-features=AutomationControlled`) y muestra una "Advertencia de
> seguridad". Para el dry-run del RPA en vivo hay que usar
> `undetected-chromedriver` o un perfil de Chrome normal; ante la duda, priorizar
> la **vía Excel de importación masiva**, que es la más segura y está sancionada
> por el SIN.

## Nota legal

El sistema **no emite** facturas nuevas: automatiza el **registro/descargo** de
documentos ya emitidos por las operadoras, operando con **credenciales propias
del contribuyente**. Uso legítimo según el marco del informe (RND N° 102100000011).
