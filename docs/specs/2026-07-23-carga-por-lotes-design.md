# Spec de diseño — Carga por lotes y control por teclas

**Fecha:** 2026-07-23 · **Autor del software:** Bryan Martínez · **Cliente:** Ing. Kevin Díaz
**Contexto:** Correcciones tras la reunión con el cliente y el dry-run contra el SIAT real.

## Problema

Registrar las tarjetas en el formulario "Agregar Registro" del RCV, de a una, es
tedioso para los contadores (100–1000 tarjetas). "Registro Masivo" del SIAT **NO
acepta Excel** (se confirmó), así que el registro debe hacerse por el formulario
individual. El objetivo es automatizar el llenado en lote **sin controlar el
navegador** (el SIN bloquea DevTools/WebDriver): solo simulación de teclado/mouse.

Además, la cuenta regresiva de 2 s presiona al usuario (queja del cliente); se
reemplaza por **control por teclas** (el usuario decide cuándo empieza/para).

## Principios

- Nada de automatización del navegador (Selenium/JS/DevTools). Solo teclado
  (pyautogui) y clics anclados por reconocimiento de imagen (pyautogui+OpenCV).
- El usuario navega manualmente hasta el formulario (el cliente lo aprobó).
- El usuario tiene el control en todo momento: inicia con **F8**, detiene con **F9**.
- Pausas tipo humano entre acciones para no disparar alertas de "movimiento
  inusual" del SIN.

## Estados de la tarjeta (nuevo modelo)

`ESTADOS = ("pendiente", "en_proceso", "completado", "saltado")`
(Se eliminan `exitoso` y `fallido` del modelo anterior; ya no aplican sin Selenium.)

- **pendiente**: leída, aún no cargada al SIAT.
- **en_proceso**: transitorio, mientras se está escribiendo/enviando.
- **completado**: cargada al SIAT. **Terminal: no se puede volver a cargar.**
- **saltado**: el usuario decidió omitirla.

Intentar cargar una `completado` muestra una **advertencia** y no la procesa. Si el
usuario aborta (F9) a mitad, la tarjeta vuelve a `pendiente`.

## Flujo 1 — Individual (botón por fila)

1. El usuario presiona el botón **"Cargar"** (verde) de la fila → el botón pasa a
   **rojo "Cancelar"** (armado). La tarjeta queda "armada" para carga.
2. Presionar el botón rojo otra vez, o **F9**, cancela → vuelve a verde.
3. El usuario navega al formulario del SIAT, hace clic en el campo **NIT Proveedor**,
   y presiona **F8** (una vez). El software escribe los campos (secuencia actual,
   sin cuenta regresiva). El usuario revisa y **presiona "Adicionar" él mismo**.
4. Al terminar de escribir, la tarjeta pasa a **completado** y el botón desaparece
   (o muestra "✓").

En el individual el software **solo llena**; el usuario mantiene el control de enviar.

**Exclusividad:** solo una tarjeta puede estar armada a la vez (armar otra fila
desarma la anterior). Los dos modos (individual armado y "Cargar todos") son
**mutuamente excluyentes**: activar uno desarma/apaga el otro. **F8** dispara el que
esté activo; **F9** apaga cualquiera.

## Flujo 2 — "Cargar todos" (botón global)

1. Botón **"Cargar todos"** verde → al presionar pasa a **rojo "Detener"** (activo).
   Presionarlo otra vez, o **F9**, cancela el modo → vuelve a verde.
2. El usuario navega al formulario, hace clic en NIT y presiona **F8** → arranca el
   **bucle** sobre las tarjetas `pendiente` (respetando el orden de la tabla):
   - marca la tarjeta `en_proceso`;
   - escribe los campos (teclado);
   - clic en **"Adicionar"** (localizado por imagen);
   - espera a que el modal se cierre (pausa humana);
   - clic en **"Nuevo Registro"** (por imagen) → el modal reabre;
   - clic en el campo **NIT** (por imagen) o confirma su auto-foco;
   - marca la tarjeta `completado` y pasa a la siguiente.
3. **Pausa:** un botón **"Pausar" / "Reanudar"** (y la tecla **F7**) suspende el
   bucle **entre tarjetas** (nunca a mitad de una); al reanudar continúa donde
   quedó. Mientras está en pausa, no escribe ni clica nada.
4. **F9 detiene** el bucle de forma limpia entre tarjetas (la actual vuelve a
   `pendiente` si no se completó). También lo detiene mover el mouse a una esquina
   (failsafe de pyautogui).
5. **Reanudar/reiniciar es seguro:** el bucle solo procesa tarjetas `pendiente`;
   las que ya quedaron `completado` **no se vuelven a tomar en cuenta** (no se
   reprocesan ni se duplican). Así, cancelar y volver a arrancar retoma desde
   donde se detuvo.
6. Al terminar (o al detener), pregunta: **"¿Guardar respaldo en Excel?"** → si sí,
   genera el Excel de las tarjetas procesadas.

**Nota (tuning del dry-run):** el orden exacto y si "Adicionar"/"Nuevo Registro" se
pueden activar por teclado en vez de por imagen se afina con 2–3 tarjetas de prueba.
El diseño soporta ambos (config), con imagen como opción robusta por defecto.

## Calibración (para "Cargar todos")

Los clics automáticos necesitan las imágenes de referencia de 3 anclas: **NIT
Proveedor**, **Adicionar**, **Nuevo Registro**. Se capturan **una vez por PC** (a
100% de zoom del navegador) con un asistente en la app:

- Un botón **"Calibrar Cargar todos"** abre el asistente.
- Para cada ancla: el usuario deja visible el formulario, la app toma una captura
  de pantalla completa y el usuario **arrastra un recuadro** sobre el elemento; la
  app guarda ese recorte en `datos/calibracion/<ancla>.png`.
- Si faltan las imágenes de calibración, "Cargar todos" avisa y ofrece calibrar.

## Selección múltiple y cambio de estado en masa

- La tabla permite **selección múltiple** (Ctrl/Shift-clic) y un botón
  **"Seleccionar todo"**.
- Un control **"Cambiar estado ▾"** aplica el estado elegido (pendiente / completado
  / saltado) a **todas las filas seleccionadas** de una vez (1, 2, 10…).

## Excel de respaldo (corregido)

El Excel ya **no** es para subir al SIAT (Registro Masivo no lo acepta): es un
**registro personal** de tarjetas usadas. Se corrige para:

- Columnas que **coinciden con el formulario real** del SIAT: `NIT Proveedor`,
  `Código de Autorización`, `Número Factura`, `Número DUI/DIM`, `Fecha Factura`,
  `Importe Total Compra`, `Importe ICE`, `Importe IEHD`, `Importe IPJ`, `Tasas`,
  `Otro No Sujeto a Crédito Fiscal`, `Importes Exentos`, `Importe Compras Gravadas
  a Tasa Cero`, `Subtotal`, `Descuentos Bonificaciones y Rebajas Sujetas al IVA`,
  `Importe Gift Card`, `Importe Base Crédito Fiscal`, `Crédito Fiscal`, `Tipo
  Compra`, `Código de Control`.
- Una columna extra **`Fecha de Registro`** = **fecha de hoy** (día en que se
  registran), para el control personal.
- Se exportan las tarjetas **completado** (las efectivamente cargadas).

## Componentes (unidades pequeñas y testeables)

| Archivo | Responsabilidad |
|---|---|
| `src/siat/atajos.py` | Escucha global de F8/F9/F7 (pynput) → callbacks/señales Qt. |
| `src/siat/localizador.py` | Carga imágenes de calibración; localiza y clica anclas (pyautogui+OpenCV). |
| `src/siat/rellenador.py` | (extiende) `cargar_registro` (ya existe) + `enviar_y_reabrir(localizador)` para el bucle. |
| `src/siat/lote.py` | Orquesta el bucle "Cargar todos": recorre pendientes, llama rellenador+localizador, respeta F9/pausas, actualiza estados vía callback. |
| `src/libro_mayor/libro_mayor.py` | Estados nuevos; `marcar` bloquea re-carga de `completado`; helper de cambio en masa. |
| `src/siat/excel_rcv.py` | Columnas corregidas + `Fecha de Registro`. |
| `src/gui/calibracion.py` | Asistente de captura de recuadro (overlay para arrastrar). |
| `src/gui/app.py` | Botón por fila (verde/rojo), "Cargar todos", modo selección + cambio en masa, wiring de F8/F9, advertencias de `completado`, prompt de Excel. |

## Manejo de errores

- **F9 / failsafe** aborta el lote entre tarjetas; la tarjeta en curso vuelve a
  `pendiente`; no se pierde el progreso de las ya `completado`.
- Si una ancla **no se encuentra en pantalla** (imagen no localizada), el lote se
  detiene con un mensaje claro ("No encontré el botón X; recalibra o revisa el
  zoom") en vez de clicar a ciegas.
- `completado` nunca se re-procesa (advertencia).
- Escritura del Libro Mayor sigue siendo atómica (ya existe).

## Testing

- **TDD (pytest, sin teclado/mouse real):**
  - `libro_mayor`: nuevo estado `completado` bloquea re-carga; cambio de estado en masa.
  - `rellenador`: `enviar_y_reabrir` llama al localizador en el orden correcto (con
    localizador falso).
  - `lote`: recorre solo `pendiente`, marca `en_proceso`→`completado`, se detiene
    ante señal de aborto, **se pausa/reanuda entre tarjetas**, no toca
    `completado`/`saltado` (con tecleador y localizador falsos).
  - `excel_rcv`: cabeceras corregidas + columna `Fecha de Registro` = hoy.
  - `atajos`: mapea F8/F9 a los callbacks (con listener falso).
- **Manual (con 2–3 tarjetas):** afinar orden real de Adicionar/Nuevo Registro/NIT.

## Fuera de alcance

- Detección de confirmación del SIAT (no se lee el navegador; `completado` = "se
  escribió y se envió", no "el SIN confirmó").
- Integración del hardware (LED ya la agregó Bryan por separado).
