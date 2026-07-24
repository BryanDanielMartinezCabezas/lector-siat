"""Interfaz gráfica (PyQt6) del Lector SIAT.

Cámara en vivo + tabla del Libro Mayor. Cada tarjeta se lee (QR/OCR), se verifica
con su foto y se edita si hace falta. El registro en el SIAT es semiautomático:
el usuario navega él mismo hasta el formulario "Agregar Registro", hace clic en el
primer campo y presiona el botón «Cargar» de esa fila; el software escribe los
campos por teclado (sin controlar el navegador, para no activar el
anti-automatización del SIN). El usuario revisa y presiona «Adicionar».
"""
import os
import sys
import traceback as _traceback
from functools import partial

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QGridLayout, QTableWidget, QTableWidgetItem, QDialog,
    QLineEdit, QFormLayout, QDialogButtonBox, QMessageBox, QFileDialog,
    QHeaderView, QComboBox, QSplitter, QSizePolicy,
)

from src.captura.camara import Camara
from src.captura.indicador_led import LedVirtual, LedHardware, LedMixto
from src.extraccion.datos_fiscales import DatosFiscales
from src.extraccion.pipeline import PipelineExtraccion
from src.extraccion.validador import validar
from src.libro_mayor.libro_mayor import LibroMayor, ESTADOS
from src.siat.periodo import fecha_declaracion
from src.siat.excel_rcv import generar_excel_compras
from src.siat.rellenador import cargar_registro, TecleadorReal
from src.siat.localizador import Localizador
from src.siat.lote import ControlLote
from src.siat.atajos import AtajosGlobales
from src.gui.hilo_lote import HiloLote

_COLORES_ESTADO = {
    "pendiente": "#d9a441", "en_proceso": "#3794d6", "completado": "#3fb950",
    "saltado": "#6e7681",
}

_CAMPOS_VALIDAR = ("nit", "numero_factura", "autorizacion", "fecha",
                   "importe", "operadora", "origen")


def _log_error(titulo: str, exc: BaseException) -> None:
    """Escribe el traceback completo en un .log junto al ejecutable.

    Útil en modo empaquetado (console=False) donde los errores son invisibles.
    """
    import datetime
    if getattr(sys, "frozen", False):
        log_path = os.path.join(os.path.dirname(sys.executable), "error_lector_siat.log")
    else:
        log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "error_lector_siat.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{datetime.datetime.now().isoformat()} — {titulo}\n")
            f.write(_traceback.format_exc())
    except Exception:
        pass  # nunca fallar por el log


# Tema oscuro moderno neutro (estilo VS Code), con tipografías y espaciados amplios.
_ESTILO = """
QMainWindow, QWidget { background: #1e1e1e; color: #d4d4d4;
    font-family: 'Segoe UI', Roboto, sans-serif; font-size: 14px; }
QLabel { color: #d4d4d4; }
QPushButton { background: #2d2d30; color: #e8e8e8; border: 1px solid #3c3c3c;
    border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #37373d; border-color: #0e7ac0; }
QPushButton:pressed { background: #094771; }
QPushButton:disabled { color: #6e6e6e; background: #262626; border-color: #2c2c2c; }
#btnPrimario { background: #0e7ac0; border-color: #0e7ac0; color: white; }
#btnPrimario:hover { background: #1a8ad4; }
#btnCargarFila { background: #167a3a; border-color: #167a3a; color: white;
    padding: 6px 10px; font-size: 12px; }
#btnCargarFila:hover { background: #1e9c4b; }
#btnRojo { background: #b3261e; border-color: #b3261e; color: white; }
#btnRojo:hover { background: #cc2e24; }
QTableWidget { background: #252526; alternate-background-color: #2a2a2b;
    color: #d4d4d4; gridline-color: #333; border: 1px solid #3c3c3c;
    border-radius: 10px; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #094771; color: white; }
QHeaderView::section { background: #2d2d30; color: #9da5b4; padding: 9px;
    border: none; border-bottom: 1px solid #3c3c3c; font-weight: 700;
    font-size: 12px; }
QComboBox, QLineEdit { background: #1a1a1a; color: #e8e8e8; border: 1px solid #3c3c3c;
    border-radius: 7px; padding: 8px; }
QComboBox:focus, QLineEdit:focus { border-color: #0e7ac0; }
QSplitter::handle { background: #2d2d30; width: 3px; }
QDialog { background: #252526; }
"""


class DialogoDetalle(QDialog):
    """Muestra la foto de la tarjeta en grande y permite editar todos los campos."""

    CAMPOS = [
        ("nit", "NIT"), ("numero_factura", "N° Factura"),
        ("autorizacion", "Código de Autorización"), ("fecha", "Fecha (dd/mm/aaaa)"),
        ("importe", "Importe (Bs)"), ("operadora", "Operadora"),
    ]

    def __init__(self, parent, tx: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Detalle {tx['id']} — verificar y editar")
        self.resize(820, 500)
        layout = QHBoxLayout(self)

        img = QLabel("(sin imagen)")
        img.setMinimumSize(420, 420)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("background:#141414;border:1px solid #3c3c3c;border-radius:8px;")
        ruta = tx.get("imagen")
        if ruta and os.path.exists(ruta):
            pix = QPixmap(ruta)
            if not pix.isNull():
                img.setPixmap(pix.scaled(420, 420, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(img, 1)

        col = QVBoxLayout()
        titulo = QLabel(f"{tx['id']} · estado: {tx['estado']}")
        titulo.setStyleSheet("font-size:16px;font-weight:700;")
        col.addWidget(titulo)
        form = QFormLayout()
        d = tx.get("datos", {})
        self.entradas = {}
        for clave, etiqueta in self.CAMPOS:
            le = QLineEdit(str(d.get(clave) or ""))
            self.entradas[clave] = le
            form.addRow(etiqueta + ":", le)
        col.addLayout(form)

        self.lbl_estado_val = QLabel()
        self.lbl_estado_val.setWordWrap(True)
        col.addWidget(self.lbl_estado_val)
        col.addStretch(1)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        col.addWidget(botones)
        layout.addLayout(col, 1)
        self._revalidar()
        for le in self.entradas.values():
            le.textChanged.connect(self._revalidar)

    def datos_editados(self) -> dict:
        base = {c: e.text().strip() or None for c, e in self.entradas.items()}
        base["origen"] = "manual"
        return base

    def _revalidar(self):
        d = self.datos_editados()
        errores = validar(DatosFiscales(**{k: d.get(k) for k in _CAMPOS_VALIDAR}))
        if errores:
            self.lbl_estado_val.setText("⚠ " + "  ·  ".join(errores))
            self.lbl_estado_val.setStyleSheet("color:#f0a020;")
        else:
            self.lbl_estado_val.setText("✔ Datos válidos.")
            self.lbl_estado_val.setStyleSheet("color:#3fb950;")


class VentanaPrincipal(QMainWindow):
    COLUMNAS = ["Tarjeta", "ID", "Estado", "NIT", "N° Factura", "Autorización",
                "Fecha", "Importe", "Cargar"]

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle("Lector SIAT — Tarjetas Prepago")
        self.resize(1360, 820)

        self.libro = LibroMayor(config["ruta_libro_mayor"])
        puerto = config.get("puerto_serial", "")
        hardware_led = LedHardware(puerto) if puerto else None
        self.led = LedMixto(LedVirtual(al_cambiar=self._pintar_led), hardware_led)
        self.pipeline = PipelineExtraccion(ocr_motor=None)  # OCR bajo demanda
        self._ocr_cargado = False
        self.camara = Camara(config.get("camara_indice", 0))
        self._cargando = False
        self._fila_armada = None
        self._modo_todos = False
        self._control = None

        self._construir_ui()
        self._iniciar_camara()
        self._refrescar_tabla()

        self._atajos = AtajosGlobales(self._f8, self._toggle_pausa, self._f9)
        try:
            self._atajos.iniciar()
        except Exception as exc:  # noqa: BLE001 - no romper el arranque sin teclado global
            _log_error("Error al iniciar atajos globales", exc)

    # ── Construcción de la interfaz ───────────────────────────────────────
    def _construir_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._panel_camara())
        splitter.addWidget(self._panel_tabla())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([520, 840])
        self.setCentralWidget(splitter)

    def _panel_camara(self) -> QWidget:
        panel = QWidget()
        izq = QVBoxLayout(panel)
        izq.setContentsMargins(14, 14, 14, 14)

        titulo_app = QLabel("Lector SIAT")
        titulo_app.setStyleSheet("font-size:22px;font-weight:700;color:#f0f0f0;")
        subtitulo = QLabel("Tarjetas prepago → Registro de Compras")
        subtitulo.setStyleSheet("font-size:12px;color:#8a8a8a;padding-bottom:8px;")
        izq.addWidget(titulo_app)
        izq.addWidget(subtitulo)

        fila_cam = QHBoxLayout()
        fila_cam.addWidget(QLabel("Cámara:"))
        self.selector_camara = QComboBox()
        self.selector_camara.currentIndexChanged.connect(self._cambiar_camara)
        fila_cam.addWidget(self.selector_camara, 1)
        self.btn_refrescar_cam = QPushButton("⟳")
        self.btn_refrescar_cam.setFixedWidth(42)
        self.btn_refrescar_cam.setToolTip("Volver a buscar cámaras")
        self.btn_refrescar_cam.clicked.connect(self._poblar_camaras)
        fila_cam.addWidget(self.btn_refrescar_cam)
        izq.addLayout(fila_cam)

        self.vista_camara = QLabel("Iniciando cámara…")
        self.vista_camara.setMinimumSize(360, 270)
        self.vista_camara.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Expanding)
        self.vista_camara.setStyleSheet(
            "background:#141414;color:#777;border:1px solid #3c3c3c;border-radius:12px;")
        self.vista_camara.setAlignment(Qt.AlignmentFlag.AlignCenter)
        izq.addWidget(self.vista_camara, 1)

        fila_led = QHBoxLayout()
        self.led_widget = QLabel()
        self.led_widget.setFixedSize(30, 30)
        self._pintar_led("apagado")
        fila_led.addWidget(self.led_widget)
        self.etiqueta_lectura = QLabel("Listo para capturar.")
        self.etiqueta_lectura.setWordWrap(True)
        self.etiqueta_lectura.setStyleSheet("font-size:13px;")
        fila_led.addWidget(self.etiqueta_lectura, 1)
        izq.addLayout(fila_led)

        self.btn_capturar = QPushButton("📸  Capturar  (Espacio)")
        self.btn_capturar.setObjectName("btnPrimario")
        self.btn_capturar.setMinimumHeight(46)
        self.btn_capturar.clicked.connect(self.capturar)
        izq.addWidget(self.btn_capturar)
        return panel

    def _panel_tabla(self) -> QWidget:
        panel = QWidget()
        der = QVBoxLayout(panel)
        der.setContentsMargins(14, 14, 14, 14)

        contadores = QGridLayout()
        contadores.setSpacing(10)
        self._labels_contador = {}
        for i, estado in enumerate(ESTADOS):
            tarjeta = QWidget()
            tarjeta.setStyleSheet(
                "background:#252526;border:1px solid #3c3c3c;border-radius:10px;")
            v = QVBoxLayout(tarjeta)
            v.setContentsMargins(8, 12, 8, 12)
            v.setSpacing(2)
            caja = QLabel("0")
            caja.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caja.setStyleSheet(
                f"background:transparent;border:none;color:{_COLORES_ESTADO[estado]};"
                "font-size:28px;font-weight:700;")
            etiq = QLabel(estado.replace("_", " ").upper())
            etiq.setAlignment(Qt.AlignmentFlag.AlignCenter)
            etiq.setStyleSheet("background:transparent;border:none;font-size:10px;"
                               "color:#8a8a8a;font-weight:700;letter-spacing:0.5px;")
            v.addWidget(caja)
            v.addWidget(etiq)
            contadores.addWidget(tarjeta, 0, i)
            self._labels_contador[estado] = caja
        der.addLayout(contadores)

        pista = QLabel("Doble clic en una fila para ver la foto en grande y editar. "
                       "Botón «Cargar» de cada fila = escribe esa tarjeta en el SIAT.")
        pista.setStyleSheet("color:#8a8a8a;font-size:11px;padding-top:4px;")
        der.addWidget(pista)

        self.tabla = QTableWidget(0, len(self.COLUMNAS))
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setHorizontalHeaderLabels(self.COLUMNAS)
        cab = self.tabla.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(len(self.COLUMNAS) - 1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.verticalHeader().setDefaultSectionSize(58)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.tabla.cellDoubleClicked.connect(self._abrir_detalle_fila)
        der.addWidget(self.tabla, 1)

        fila_lote = QHBoxLayout()
        self.btn_todos = QPushButton("▶ Cargar todos")
        self.btn_todos.setObjectName("btnPrimario")
        self.btn_todos.clicked.connect(self._toggle_cargar_todos)
        self.btn_pausar = QPushButton("⏸ Pausar")
        self.btn_pausar.setEnabled(False)
        self.btn_pausar.clicked.connect(self._toggle_pausa)
        self.btn_sel_todo = QPushButton("Seleccionar todo")
        self.btn_sel_todo.clicked.connect(self.tabla.selectAll)
        self.btn_estado = QPushButton("Marcar saltado (sel.)")
        self.btn_estado.clicked.connect(lambda: self._estado_masa("saltado"))
        self.btn_calibrar = QPushButton("⚙ Calibrar")
        self.btn_calibrar.clicked.connect(self._calibrar)
        for b in (self.btn_todos, self.btn_pausar, self.btn_sel_todo,
                  self.btn_estado, self.btn_calibrar):
            fila_lote.addWidget(b)
        fila_lote.addStretch(1)
        der.addLayout(fila_lote)

        acciones = QHBoxLayout()
        self.btn_ver = QPushButton("🔍 Ver / Editar")
        self.btn_ver.clicked.connect(self._abrir_detalle_seleccion)
        self.btn_excel = QPushButton("⬇ Exportar Excel RCV")
        self.btn_excel.clicked.connect(self.exportar_excel)
        self.btn_saltar = QPushButton("⏭ Saltado")
        self.btn_saltar.clicked.connect(lambda: self._cambiar_estado_seleccion("saltado"))
        self.btn_reintentar = QPushButton("↺ Reintentar")
        self.btn_reintentar.clicked.connect(lambda: self._cambiar_estado_seleccion("pendiente"))
        self.btn_borrar = QPushButton("🗑 Borrar")
        self.btn_borrar.clicked.connect(self._borrar_seleccion)
        self.btn_vaciar = QPushButton("Vaciar todo")
        self.btn_vaciar.clicked.connect(self._vaciar_libro)
        for b in (self.btn_ver, self.btn_excel, self.btn_saltar,
                  self.btn_reintentar, self.btn_borrar, self.btn_vaciar):
            acciones.addWidget(b)
        acciones.addStretch(1)
        der.addLayout(acciones)
        return panel

    # ── Cámara ────────────────────────────────────────────────────────────
    def _iniciar_camara(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._actualizar_frame)
        self._poblar_camaras()

    def _poblar_camaras(self):
        self.selector_camara.blockSignals(True)
        self.selector_camara.clear()
        indices = Camara.listar_camaras()
        if not indices:
            self.selector_camara.addItem("Sin cámara", -1)
            self.vista_camara.setText("Cámara no disponible\n(usa captura de archivo)")
        else:
            for idx in indices:
                etiqueta = "Cámara 0 (interna)" if idx == 0 else f"Cámara {idx} (DroidCam/USB)"
                self.selector_camara.addItem(etiqueta, idx)
        self.selector_camara.blockSignals(False)
        if indices:
            self._cambiar_camara()

    def _cambiar_camara(self):
        indice = self.selector_camara.currentData()
        if indice is None or indice < 0:
            return
        self._timer.stop()
        if self.camara.cambiar_a(indice):
            self.etiqueta_lectura.setText(f"Cámara {indice} activa. Listo para capturar.")
            self._timer.start(33)  # ~30 fps
        else:
            self.vista_camara.setText(f"No se pudo abrir la cámara {indice}.")

    def _actualizar_frame(self):
        frame = self.camara.leer_frame()
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self.vista_camara.setPixmap(QPixmap.fromImage(img).scaled(
            self.vista_camara.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.capturar()

    # ── Captura + extracción ──────────────────────────────────────────────
    def _asegurar_ocr(self):
        if not self._ocr_cargado:
            self._ocr_cargado = True  # marcar antes para no reintentar en loop
            try:
                from src.extraccion.ocr_motor import OcrMotor
                self.pipeline = PipelineExtraccion(
                    ocr_motor=OcrMotor(self.config["ruta_modelos_ocr"]))
            except Exception as exc:
                import traceback
                self.etiqueta_lectura.setText(
                    f"⚠ OCR no disponible: {exc}. Se usará solo QR.")
                # Loguear el error completo en un archivo junto al .exe
                _log_error("Error al cargar OCR", exc)
                self.pipeline = PipelineExtraccion(ocr_motor=None)

    def capturar(self):
        try:
            self._capturar_impl()
        except Exception as exc:
            import traceback
            detalle = traceback.format_exc()
            _log_error("Error en capturar()", exc)
            QMessageBox.critical(
                self, "Error al capturar",
                f"{type(exc).__name__}: {exc}\n\n"
                "Revisa el archivo error_lector_siat.log junto al ejecutable."
            )

    def _capturar_impl(self):
        frame = self.camara.leer_frame()
        if frame is None:
            ruta, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar imagen de tarjeta", "", "Imágenes (*.png *.jpg *.jpeg)")
            if not ruta:
                return
            frame = cv2.imread(ruta)
        else:
            os.makedirs(self.config["ruta_capturas"], exist_ok=True)
            ruta = self.camara.nombre_captura(self.config["ruta_capturas"])
            cv2.imwrite(ruta, frame)

        self._asegurar_ocr()
        resultado = self.pipeline.procesar_imagen(frame)
        # Las tarjetas se declaran con el 01 del mes vigente (no con su fecha impresa).
        resultado.datos.fecha = fecha_declaracion(
            self.config.get("periodo_declaracion") or None)
        tx = self.libro.agregar(resultado.datos, imagen=ruta)
        if resultado.es_valido:
            self.led.verde()
            self.etiqueta_lectura.setText(
                f"✔ {tx} [{resultado.metodo}] NIT {resultado.datos.nit} · "
                f"Bs {resultado.datos.importe}")
        else:
            self.led.rojo()
            self.etiqueta_lectura.setText(
                f"⚠ {tx} necesita revisión: {'; '.join(resultado.errores)}. "
                "Doble clic en la fila para corregir.")
        self._refrescar_tabla()

    # ── LED + tabla + contadores ──────────────────────────────────────────
    def _pintar_led(self, color: str):
        mapa = {"verde": "#22c55e", "rojo": "#ef4444", "apagado": "#333"}
        self.led_widget.setStyleSheet(
            f"background:{mapa.get(color, '#333')};border-radius:15px;")

    def _refrescar_tabla(self):
        transacciones = self.libro.todas()
        self.tabla.setRowCount(len(transacciones))
        for fila, tx in enumerate(transacciones):
            d = tx["datos"]

            mini = QLabel()
            mini.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ruta = tx.get("imagen")
            if ruta and os.path.exists(ruta):
                pix = QPixmap(ruta)
                if not pix.isNull():
                    mini.setPixmap(pix.scaled(76, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
            else:
                mini.setText("—")
            self.tabla.setCellWidget(fila, 0, mini)

            invalido = bool(validar(DatosFiscales(**{k: d.get(k) for k in _CAMPOS_VALIDAR})))
            estado_txt = tx["estado"] + ("  ⚠" if invalido else "")
            valores = [tx["id"], estado_txt, d.get("nit", ""),
                       d.get("numero_factura", ""), d.get("autorizacion", ""),
                       d.get("fecha", ""), d.get("importe", "")]
            for offset, val in enumerate(valores):
                item = QTableWidgetItem(str(val or ""))
                if invalido:
                    item.setForeground(Qt.GlobalColor.red)
                self.tabla.setItem(fila, offset + 1, item)

            # Última columna: botón «Cargar» propio de la fila (armar/cancelar).
            btn = QPushButton("Cargar")
            completado = tx["estado"] == "completado"
            armada = (self._fila_armada == tx["id"])
            if completado:
                btn.setText("✓ Completado")
                btn.setEnabled(False)
            elif armada:
                btn.setObjectName("btnRojo")
                btn.setText("✖ Cancelar")
            else:
                btn.setObjectName("btnCargarFila")
                btn.setText("⌨ Cargar")
                btn.setEnabled(not invalido and not self._cargando)
            btn.setToolTip("Arma esta tarjeta; luego clic en NIT del SIAT y F8.")
            btn.clicked.connect(partial(self._toggle_armar_fila, tx["id"]))
            self.tabla.setCellWidget(fila, len(self.COLUMNAS) - 1, btn)

        c = self.libro.contadores()
        for estado, label in self._labels_contador.items():
            label.setText(str(c[estado]))

    def _tx_por_id(self, tx_id: str) -> dict | None:
        return next((t for t in self.libro.todas() if t["id"] == tx_id), None)

    def _tx_de_fila(self, fila: int) -> dict | None:
        if fila < 0:
            return None
        item = self.tabla.item(fila, 1)  # columna ID
        return self._tx_por_id(item.text()) if item else None

    def _abrir_detalle_fila(self, fila: int, _col: int = 0):
        tx = self._tx_de_fila(fila)
        if tx is None:
            return
        dlg = DialogoDetalle(self, tx)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.libro.actualizar_datos(tx["id"], dlg.datos_editados())
            self._refrescar_tabla()

    def _abrir_detalle_seleccion(self):
        self._abrir_detalle_fila(self.tabla.currentRow())

    def _borrar_seleccion(self):
        tx = self._tx_de_fila(self.tabla.currentRow())
        if tx is None:
            return
        if QMessageBox.question(self, "Borrar",
                                f"¿Borrar la transacción {tx['id']}?"
                                ) == QMessageBox.StandardButton.Yes:
            self.libro.eliminar(tx["id"])
            self._refrescar_tabla()

    def _vaciar_libro(self):
        if QMessageBox.question(
                self, "Vaciar todo",
                "¿Borrar TODAS las transacciones del Libro Mayor? No se puede deshacer."
                ) == QMessageBox.StandardButton.Yes:
            self.libro.vaciar()
            self._refrescar_tabla()

    def _cambiar_estado_seleccion(self, estado: str):
        tx = self._tx_de_fila(self.tabla.currentRow())
        if tx is None:
            return
        self.libro.marcar(tx["id"], estado, "Cambio manual desde la GUI.")
        self._refrescar_tabla()

    # ── Motor "Cargar" por fila (armar + F8, teclado real del SIAT) ───────
    def _toggle_armar_fila(self, tx_id: str):
        if not self.libro.puede_cargar(tx_id):
            QMessageBox.warning(self, "Ya completada",
                                "Esta tarjeta ya fue cargada. No se puede volver a cargar.")
            return
        self._modo_todos = False
        self._fila_armada = None if self._fila_armada == tx_id else tx_id
        self.etiqueta_lectura.setText(
            "Ve al formulario, clic en NIT y presiona F8." if self._fila_armada
            else "Carga individual cancelada.")
        self._refrescar_tabla()

    # ── Selección múltiple y estado en masa ────────────────────────────────
    def _ids_seleccionados(self) -> list[str]:
        ids = []
        for idx in self.tabla.selectionModel().selectedRows(1):
            ids.append(idx.data())
        return ids

    def _estado_masa(self, estado: str):
        ids = self._ids_seleccionados()
        if not ids:
            QMessageBox.information(self, "Selección", "Selecciona una o más filas.")
            return
        self.libro.marcar_varias(ids, estado)
        self._refrescar_tabla()

    # ── Calibración ─────────────────────────────────────────────────────────
    def _calibrar(self):
        from src.gui.calibracion import calibrar_anclas
        ruta = self.config.get("ruta_calibracion", "datos/calibracion")
        if calibrar_anclas(self, ruta):
            QMessageBox.information(self, "Calibración", "Listo, las 3 imágenes se guardaron.")

    # ── Modo "Cargar todos" (lote automático) ──────────────────────────────
    def _toggle_cargar_todos(self):
        ruta = self.config.get("ruta_calibracion", "datos/calibracion")
        loc = Localizador(ruta)
        if not loc.disponible():
            QMessageBox.warning(self, "Falta calibrar",
                                "Primero presiona «Calibrar» (una vez por PC).")
            return
        self._fila_armada = None
        self._modo_todos = not self._modo_todos
        self.btn_todos.setText("■ Detener modo" if self._modo_todos else "▶ Cargar todos")
        self.etiqueta_lectura.setText(
            "Ve al formulario, clic en NIT y presiona F8." if self._modo_todos
            else "Modo Cargar todos apagado.")

    def _toggle_pausa(self):
        if self._control is None:
            return
        if self._control.esta_pausado():
            self._control.reanudar()
            self.btn_pausar.setText("⏸ Pausar")
        else:
            self._control.pausar()
            self.btn_pausar.setText("▶ Reanudar")

    # ── Atajos globales: F8 iniciar, F7 pausar/reanudar, F9 detener ───────
    def _f8(self):
        if self._modo_todos:
            self._control = ControlLote()
            self.btn_pausar.setEnabled(True)
            self._cargando = True
            self._refrescar_tabla()
            self._hilo = HiloLote(self.libro, self._control, self.config)
            self._hilo.cambio.connect(lambda *_: self._refrescar_tabla())
            self._hilo.terminado.connect(self._lote_termino)
            self._hilo.start()
        elif self._fila_armada:
            tx = self._tx_por_id(self._fila_armada)
            cargar_registro(tx["datos"], TecleadorReal(
                float(self.config.get("carga_intervalo_tecla", 0.05))),
                pausa=float(self.config.get("carga_pausa_campo", 0.35)))
            self.libro.marcar(self._fila_armada, "completado")
            self.etiqueta_lectura.setText(f"✔ {self._fila_armada} escrita. Presiona Adicionar.")
            self._fila_armada = None
            self._refrescar_tabla()

    def _f9(self):
        if self._control is not None:
            self._control.abortar()
        self._fila_armada = None
        self._modo_todos = False
        self.btn_todos.setText("▶ Cargar todos")

    def _lote_termino(self, resumen: dict):
        self._cargando = False
        self._modo_todos = False
        self._control = None
        self.btn_pausar.setEnabled(False)
        self.btn_todos.setText("▶ Cargar todos")
        self._refrescar_tabla()
        if resumen["completado"] and QMessageBox.question(
                self, "Respaldo", "¿Guardar un Excel con las tarjetas cargadas?"
                ) == QMessageBox.StandardButton.Yes:
            self._exportar_completadas()

    def _exportar_completadas(self):
        comp = [t for t in self.libro.todas() if t["estado"] == "completado"]
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Excel", "compras_rcv.xlsx", "Excel (*.xlsx)")
        if ruta:
            generar_excel_compras(comp, ruta)
            QMessageBox.information(self, "Excel", f"Guardadas {len(comp)} tarjetas.")

    # ── Excel ─────────────────────────────────────────────────────────────
    def exportar_excel(self):
        pendientes = self.libro.pendientes()
        if not pendientes:
            QMessageBox.information(self, "Excel RCV", "No hay pendientes para exportar.")
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel RCV", "compras_rcv.xlsx", "Excel (*.xlsx)")
        if not ruta:
            return
        filas = generar_excel_compras(pendientes, ruta)
        QMessageBox.information(self, "Excel RCV", f"Se exportaron {filas} compras a:\n{ruta}")

    def closeEvent(self, event):
        try:
            self._atajos.detener()
        except Exception as exc:  # noqa: BLE001 - no bloquear el cierre
            _log_error("Error al detener atajos globales", exc)
        self.camara.cerrar()
        super().closeEvent(event)


def lanzar(config: dict):
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_ESTILO)
    ventana = VentanaPrincipal(config)
    ventana.show()
    app.exec()
