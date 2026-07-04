# Spec de diseño — Lector SIAT (software de la cajita)

**Fecha:** 2026-07-04 · **Autor del software:** Bryan Martínez (con Claude) · **Hardware:** Adrián Ovando
**Base:** Informe de Planificación aprobado (Robótica II, COM480) + código reciclado de Bolifactura-app.

## Principio rector (condición de aprobación)

> **Nosotros nos acoplamos a la página del SIAT; la página no se acopla a nosotros.**

Todo formulario del mock se construye inspeccionando el portal real con Playwright y replicando su
HTML/CSS/disposición. Los selectores del RPA se validan contra la página real cada vez que se toque
el mock o el ejecutor. Referencias capturadas del portal real viven en `referencia_siat/`
(HTML y screenshot del login v2 ya capturados el 2026-07-04).

## Objetivo

Software de escritorio (Windows, Python 3.11+) que: captura el reverso de tarjetas prepago
(Entel/Tigo/Viva) con cámara USB, extrae los datos fiscales (QR primero, OCR de respaldo),
los guarda en un Libro Mayor JSON con máquina de estados, y los registra en el RCV del SIAT
por dos vías: RPA Selenium individual (principal, según informe) y archivo Excel de importación
masiva (respaldo). GUI en PyQt6. El disparo por sensor IR y los LEDs quedan desacoplados tras
interfaces para integrarse cuando la cajita física esté lista.

## Decisiones tomadas

| Decisión | Elección | Motivo |
|---|---|---|
| Vía al SIAT | Ambas: Selenium individual + generador Excel RCV | Informe exige RPA resiliente; Excel es plan B robusto |
| Entorno de prueba RPA | Mock local Flask **fiel al portal real** | Dry-run contra el SIAT real "horas después" de validar |
| GUI | PyQt6 | Tablas, cámara embebida, hilos; mejor para la defensa |
| OCR | PaddleOCR v4 (modelos ya en `modelos_ocr/`, offline) | Ya venía armado en el repo de Adrián; ML Kit es solo móvil |
| QR | pyzbar (+ fallback detector QR de OpenCV) | Según informe |
| Datos | `datos/libro_mayor.json`, escritura atómica | Según informe |

## Arquitectura

```
lector-siat/
├── config/
│   ├── config.json            # cámara, lote (5), timeout (60 s), rutas
│   └── selectores_siat.json   # perfiles "mock" y "real": URLs + selectores CSS
├── modelos_ocr/               # PaddleOCR det+rec+diccionario (de recuperado/)
├── referencia_siat/           # capturas Playwright del portal real (HTML+PNG)
├── datos/                     # libro_mayor.json + capturas/
├── src/
│   ├── captura/
│   │   ├── camara.py          # OpenCV: stream, foto
│   │   └── disparador.py      # ABC Disparador → DisparadorTeclado | DisparadorSensorIR(serial)
│   ├── extraccion/
│   │   ├── qr_lector.py       # pyzbar + parse del contenido QR (NIT+autorización seguido)
│   │   ├── ocr_motor.py       # wrapper PaddleOCR → lista de líneas de texto
│   │   ├── extractor_fiscal.py# port Python del motor v4 de ocr_service.dart (regex bolivianas)
│   │   └── validador.py       # NIT 7-11 dígitos, NITs operadoras conocidas, fecha, importe > 0
│   ├── libro_mayor/
│   │   └── libro_mayor.py     # estados: pendiente|en_proceso|exitoso|fallido|saltado
│   ├── siat/
│   │   ├── rpa_selenium.py    # lotes de 5, esperas explícitas, timeout 60 s, stop-on-failure, relogueo
│   │   └── excel_rcv.py       # Excel con columnas oficiales de importación masiva del RCV
│   ├── gui/app.py             # PyQt6: cámara, contadores por estado, tabla, botones, LED virtual
│   └── main.py
├── mock_siat/
│   ├── servidor.py            # Flask: login réplica Keycloak v2 + menú + form registro compra
│   ├── templates/             # HTML copiado/adaptado del portal real
│   └── static/                # CSS extraído del portal real
└── tests/                     # pytest: extractor, validador, libro_mayor, excel_rcv
```

## Datos del portal real ya capturados (login v2)

- URL real: `https://siat.impuestos.gob.bo/` → redirige a Keycloak `login.impuestos.gob.bo/realms/login2/...`
- Form `#kc-form-login` con: `input#nitCur` (placeholder "Ejm: 123456-1X o 123456-78"),
  `input#email`, `input#password`, hidden `#deviceId`, botón `button#kc-login` ("INGRESAR").
- Estética: fondo teal oscuro con patrón de circuitos, tarjeta central borde neón,
  título "IMPUESTOS NACIONALES", subtítulo "Inicia sesión", links chip
  ("Olvide mi contraseña", "Iniciar sesión en OVT/SIAT v1", "Registrarme como Ciudadano").
- El formulario de **registro de compras del RCV** está tras el login (no accesible sin
  credenciales). El mock lo construye con los campos oficiales del formato de importación
  masiva documentado por el SIN: NIT proveedor, razón social, código de autorización,
  número de factura, fecha (dd/mm/aaaa), importe total, tipo de compra (1|2), código de
  control (hexadecimal con guiones, "0" si no aplica). **Pendiente marcado:** el día que Bryan
  tenga credenciales, capturar con Playwright el formulario real logueado y ajustar el mock
  + `selectores_siat.json` perfil "real".

## Flujo de datos

1. `camara.py` muestra stream; `disparador` (tecla ahora, sensor IR luego) ordena capturar.
2. `qr_lector` intenta decodificar QR → si obtiene NIT+autorización, listo.
3. Si falla, `ocr_motor` (PaddleOCR) → líneas → `extractor_fiscal` (regex portadas).
4. `validador` verifica campos; feedback LED virtual verde/rojo (interfaz `IndicadorLed`).
5. Registro entra al Libro Mayor como `pendiente` (escritura atómica: tmp + `os.replace`).
6. `rpa_selenium` procesa pendientes en lotes de 5: login → formulario → esperar confirmación
   explícita → `exitoso`; timeout 60 s o error → `fallido` + **detener todo** preservando estado.
   Relogueo entre lotes. Al reiniciar retoma el primer `pendiente`.
7. Alternativa: `excel_rcv` exporta pendientes al Excel oficial para importación masiva manual.

## Manejo de errores

- Libro Mayor nunca se corrompe (escritura atómica) ni duplica envíos (estados).
- El RPA jamás reintenta un `fallido` automáticamente: el operario lo corrige y lo marca
  `saltado` o lo devuelve a `pendiente` desde la GUI.
- Toda operación Selenium usa `WebDriverWait` (esperas explícitas), nunca `sleep` fijos.
- El mock simula lentitud aleatoria (2–15 s) y errores de servidor (~10%) para probar resiliencia.

## Testing

- **TDD (pytest)**: `extractor_fiscal` (fixtures de texto OCR de tarjetas reales de las 3
  operadoras), `validador`, `libro_mayor` (transiciones, reanudación, atomicidad), `excel_rcv`.
- **E2E**: RPA completo contra el mock, incluyendo fallos inyectados.
- **Dry-run** (futuro, con credenciales): perfil "real" con envío final deshabilitado.

## Fuera de alcance

Integración física del sensor IR/LEDs (Adrián), servicios SOAP del SIN, emisión de facturas,
empaquetado final PyInstaller/NSSM (se hará al cierre, está descrito en el informe).
