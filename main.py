"""
Snipping Tool - Screenshot-Anwendung mit PyQt5
----------------------------------------------
Ein leichtgewichtiges Tool zum Erstellen von Screenshots mit verschiedenen Aufnahmemodi,
Verzögerungsoption und direkter Speicher- sowie Kopier-Funktionalität.

Unterstützte Aufnahmemodi:
- Rechteckiger Ausschnitt
- Freiform-Ausschnitt
- Fenster-Ausschnitt
- Vollbild-Ausschnitt

Abhängigkeiten:
- PyQt5 für die GUI
- gnome-screenshot für die Screenshot-Funktionalität
- xclip für Zwischenablage-Unterstützung
"""
import sys
import os
import subprocess
import tempfile
from datetime import datetime
from PyQt5.QtCore import Qt, QRect, QPoint, QSize, QTimer, pyqtSignal, QRectF
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QPixmap, QIcon, QFont,
    QPainterPath, QCursor, QImage, QRadialGradient
)
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QAction, QFileDialog,
    QShortcut, QToolBar, QPushButton, QLabel, QComboBox,
    QVBoxLayout, QHBoxLayout, QSpinBox, QStatusBar, QMenu,
    QMessageBox, QSizePolicy, QSlider, QColorDialog, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QFrame, QButtonGroup, QToolButton
)


class ColorButton(QPushButton):
    """Farbauswahlknopf mit Farbvorschau"""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setColor(color)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self.choose_color)

    def setColor(self, color):
        self.color = color
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setBrush(QBrush(self.color))
        painter.drawRoundedRect(rect, 5, 5)

    def choose_color(self):
        color = QColorDialog.getColor(self.color, self)
        if color.isValid():
            self.setColor(color)
            self.update()


class DrawingTool:
    PEN = 1
    MARKER = 2
    ERASER = 3
    TEXT = 4
    RECTANGLE = 5
    ELLIPSE = 6
    ARROW = 7


class EditableScene(QGraphicsScene):
    """Bearbeitbare Grafikszene für den Screenshot"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = None
        self.last_point = None
        self.current_tool = DrawingTool.PEN
        self.current_color = QColor("#ff0000")
        self.current_width = 2
        self.temp_item = None
        self.start_point = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_point = event.scenePos()
            self.start_point = event.scenePos()

            if self.current_tool in [DrawingTool.PEN, DrawingTool.MARKER]:
                self.current_path = QPainterPath()
                self.current_path.moveTo(self.last_point)
            elif self.current_tool in [DrawingTool.RECTANGLE, DrawingTool.ELLIPSE, DrawingTool.ARROW]:
                # Temporäres Item für Vorschau erstellen
                if self.current_tool == DrawingTool.RECTANGLE:
                    self.temp_item = self.addRect(
                        QRectF(self.start_point, self.start_point),
                        QPen(self.current_color, self.current_width),
                        QBrush(Qt.NoBrush)
                    )
                elif self.current_tool == DrawingTool.ELLIPSE:
                    self.temp_item = self.addEllipse(
                        QRectF(self.start_point, self.start_point),
                        QPen(self.current_color, self.current_width),
                        QBrush(Qt.NoBrush)
                    )

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.last_point:
            point = event.scenePos()

            if self.current_tool in [DrawingTool.PEN, DrawingTool.MARKER]:
                # Bei Stift und Marker: Linie zeichnen
                self.current_path.lineTo(point)

                # Aktuellen Pfad entfernen und neu zeichnen
                if hasattr(self, 'path_item') and self.path_item in self.items():
                    self.removeItem(self.path_item)

                pen = QPen(self.current_color, self.current_width)

                if self.current_tool == DrawingTool.MARKER:
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    pen.setColor(QColor(self.current_color.red(),
                                        self.current_color.green(),
                                        self.current_color.blue(),
                                        100))  # Semi-transparent

                self.path_item = self.addPath(self.current_path, pen)

            elif self.current_tool == DrawingTool.ERASER:
                # Radiergummi: Elemente unter dem Cursor entfernen
                items = self.items(point)
                for item in items:
                    if isinstance(item, (QGraphicsPathItem, QGraphicsEllipseItem)) and item != self.temp_item:
                        self.removeItem(item)

            elif self.current_tool in [DrawingTool.RECTANGLE, DrawingTool.ELLIPSE, DrawingTool.ARROW]:
                # Vorschau für Rechteck oder Ellipse aktualisieren
                rect = QRectF(self.start_point, point).normalized()
                if self.current_tool == DrawingTool.RECTANGLE and self.temp_item:
                    self.temp_item.setRect(rect)
                elif self.current_tool == DrawingTool.ELLIPSE and self.temp_item:
                    self.temp_item.setRect(rect)
                elif self.current_tool == DrawingTool.ARROW and self.temp_item:
                    # Arrow wird als Linie mit Pfeilspitze implementiert
                    # Hier könnte eine komplexere Implementation folgen
                    pass

            self.last_point = point

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.current_tool in [DrawingTool.RECTANGLE, DrawingTool.ELLIPSE, DrawingTool.ARROW]:
                # Temporäres Item freigeben
                self.temp_item = None

            self.last_point = None

        super().mouseReleaseEvent(event)


class EditorWidget(QWidget):
    """Widget zur Bearbeitung des aufgenommenen Screenshots"""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setupUI()

    def setupUI(self):
        # Hauptlayout
        layout = QVBoxLayout(self)

        # Haupt-Toolbar für Zeichenwerkzeuge
        toolbar = QToolBar("Zeichenwerkzeuge")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)  # Text unter dem Icon

        # Werkzeugbuttons erstellen
        tool_group = QButtonGroup(self)

        # Werkzeuge mit Icons erstellen
        self.pen_button = QToolButton()
        self.pen_button.setText("Stift")
        self.pen_button.setCheckable(True)
        self.pen_button.setChecked(True)
        tool_group.addButton(self.pen_button, DrawingTool.PEN)

        self.marker_button = QToolButton()
        self.marker_button.setText("Marker")
        self.marker_button.setCheckable(True)
        tool_group.addButton(self.marker_button, DrawingTool.MARKER)

        self.eraser_button = QToolButton()
        self.eraser_button.setText("Radiergummi")
        self.eraser_button.setCheckable(True)
        tool_group.addButton(self.eraser_button, DrawingTool.ERASER)

        self.rectangle_button = QToolButton()
        self.rectangle_button.setText("Rechteck")
        self.rectangle_button.setCheckable(True)
        tool_group.addButton(self.rectangle_button, DrawingTool.RECTANGLE)

        self.ellipse_button = QToolButton()
        self.ellipse_button.setText("Ellipse")
        self.ellipse_button.setCheckable(True)
        tool_group.addButton(self.ellipse_button, DrawingTool.ELLIPSE)

        toolbar.addWidget(self.pen_button)
        toolbar.addWidget(self.marker_button)
        toolbar.addWidget(self.eraser_button)
        toolbar.addWidget(self.rectangle_button)
        toolbar.addWidget(self.ellipse_button)
        toolbar.addSeparator()

        # Farbauswahl
        self.color_button = ColorButton(QColor("#ff0000"))
        toolbar.addWidget(self.color_button)

        # Strichstärke
        toolbar.addWidget(QLabel("Stärke:"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 20)
        self.width_slider.setValue(2)
        self.width_slider.setFixedWidth(100)
        toolbar.addWidget(self.width_slider)

        layout.addWidget(toolbar)

        # Zweite Toolbar für Speichern/Kopieren
        action_toolbar = QToolBar("Aktions-Werkzeuge")
        action_toolbar.setIconSize(QSize(32, 32))
        action_toolbar.setMovable(False)

        # Speichern/Kopieren-Buttons mit Icon und Text
        save_action = QAction("Speichern", self)
        save_action.setIcon(QIcon.fromTheme("document-save"))
        save_action.triggered.connect(self.save_image)
        action_toolbar.addAction(save_action)

        copy_action = QAction("Kopieren", self)
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(self.copy_to_clipboard)
        action_toolbar.addAction(copy_action)

        layout.addWidget(action_toolbar)

        # Grafikansicht für den Screenshot
        self.view = QGraphicsView()
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setBackgroundBrush(QBrush(QColor("#f0f0f0")))
        self.view.setFrameShape(QFrame.NoFrame)

        self.scene = EditableScene()
        self.view.setScene(self.scene)

        # Bild laden
        self.pixmap = QPixmap(self.image_path)
        self.pixmap_item = self.scene.addPixmap(self.pixmap)
        self.scene.setSceneRect(QRectF(self.pixmap.rect()))

        layout.addWidget(self.view)

        # Werkzeugauswahl verbinden
        tool_group.buttonClicked.connect(self.set_tool)
        self.color_button.clicked.connect(self.set_color)
        self.width_slider.valueChanged.connect(self.set_width)

    def set_tool(self, button):
        self.scene.current_tool = self.sender().id(button)

    def set_color(self):
        self.scene.current_color = self.color_button.color

    def set_width(self, width):
        self.scene.current_width = width

    def save_image(self):
        # Screenshot mit Zeichnungen als Bild speichern
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Screenshot speichern",
            f"Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;All Files (*)"
        )

        if filepath:
            # Szene in Pixmap rendern
            image = QImage(self.pixmap.size(), QImage.Format_ARGB32)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            self.scene.render(painter)
            painter.end()

            # Speichern
            image.save(filepath)
            QMessageBox.information(self, "Gespeichert", f"Screenshot wurde gespeichert unter:\n{filepath}")

    def copy_to_clipboard(self):
        # Szene in Pixmap rendern
        image = QImage(self.pixmap.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        self.scene.render(painter)
        painter.end()

        # In temporäre Datei speichern
        temp_file = tempfile.mktemp(suffix='.png')
        image.save(temp_file)

        # Mit xclip in Zwischenablage kopieren
        try:
            subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', temp_file])
            QMessageBox.information(self, "Kopiert", "Screenshot wurde in die Zwischenablage kopiert.")
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Kopieren: {str(e)}")


class CountdownOverlay(QWidget):
    """Overlay für den Countdown vor dem Screenshot"""

    finished = pyqtSignal()

    def __init__(self, seconds, parent=None):
        super().__init__(parent)
        self.seconds = seconds
        self.current = seconds

        # Fenstereinstellungen
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent;")

        # Bildschirmgröße bestimmen
        desktop = QApplication.desktop()
        screen_rect = desktop.screenGeometry()
        self.setGeometry(screen_rect)

        # Timer einrichten
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def paintEvent(self, event):
        if self.current <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Halbdurchsichtiger Hintergrund
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

        # Countdown-Zahl
        font = QFont("Arial", 100, QFont.Bold)
        painter.setFont(font)

        # Verlaufsfüllung für den Text
        gradient = QRadialGradient(self.rect().center(), 100)
        gradient.setColorAt(0, QColor(255, 255, 255))
        gradient.setColorAt(1, QColor(200, 200, 255))
        painter.setBrush(QBrush(gradient))

        # Schatten für den Text
        painter.setPen(QPen(QColor(0, 0, 0, 180), 2))
        painter.drawText(self.rect().adjusted(3, 3, 3, 3), Qt.AlignCenter, str(self.current))

        # Text
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self.current))

    def update_countdown(self):
        self.current -= 1
        self.update()

        if self.current <= 0:
            self.timer.stop()
            self.hide()
            self.finished.emit()


class SnippingTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Fenstereinstellungen
        self.setWindowTitle("MS Snipping Tool Clone")
        self.setGeometry(100, 100, 600, 300)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QToolBar {
                background-color: #f0f0f0;
                border-bottom: 1px solid #e0e0e0;
                spacing: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QToolButton {
                background-color: #e6e6e6;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:checked {
                background-color: #0078d7;
                color: white;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                min-width: 180px;
                background-color: white;
            }
            QSpinBox {
                padding: 5px;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: white;
            }
            QLabel {
                padding: 0px 5px;
            }
            QStatusBar {
                background-color: #f0f0f0;
                color: #505050;
            }
        """)

        # Icon
        self.setWindowIcon(self.create_icon())

        # Hauptlayout erstellen
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Toolbar erstellen
        self.toolbar = QToolBar("Hauptwerkzeugleiste")
        self.addToolBar(self.toolbar)

        # Mode-Icon und Beschriftung
        mode_label = QLabel("Modus:")
        mode_label.setFont(QFont("Segoe UI", 9))
        self.toolbar.addWidget(mode_label)

        # Screenshot-Typ-Auswahl
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Rechteckiger Ausschnitt",
            "Freiform-Ausschnitt",
            "Fenster-Ausschnitt",
            "Vollbild-Ausschnitt"
        ])
        self.mode_combo.setCurrentIndex(0)
        self.toolbar.addWidget(self.mode_combo)
        self.toolbar.addSeparator()

        # Verzögerung
        delay_label = QLabel("Verzögerung:")
        delay_label.setFont(QFont("Segoe UI", 9))
        self.toolbar.addWidget(delay_label)

        self.delay_spinner = QSpinBox()
        self.delay_spinner.setRange(0, 10)
        self.delay_spinner.setSuffix(" Sek.")
        self.toolbar.addWidget(self.delay_spinner)
        self.toolbar.addSeparator()

        # Optionen
        options_label = QLabel("Optionen:")
        options_label.setFont(QFont("Segoe UI", 9))
        self.toolbar.addWidget(options_label)

        self.incl_cursor_button = QToolButton()
        self.incl_cursor_button.setText("Cursor einschließen")
        self.incl_cursor_button.setCheckable(True)
        self.toolbar.addWidget(self.incl_cursor_button)
        self.toolbar.addSeparator()

        # Haupt-Aktion-Button
        self.new_button = QPushButton("Neu")
        self.new_button.setIcon(self.style().standardIcon(self.style().SP_DialogSaveButton))
        self.new_button.clicked.connect(self.take_screenshot)
        self.toolbar.addWidget(self.new_button)

        # Informations-Inhaltsbereich
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        # Logo und Titel
        logo_layout = QHBoxLayout()

        logo_label = QLabel()
        logo_pixmap = QPixmap(32, 32)
        logo_pixmap.fill(Qt.transparent)
        logo_painter = QPainter(logo_pixmap)
        logo_painter.setRenderHint(QPainter.Antialiasing)
        self.draw_icon(logo_painter, logo_pixmap.rect())
        logo_painter.end()
        logo_label.setPixmap(logo_pixmap)
        logo_layout.addWidget(logo_label)

        info_title = QLabel("MS Snipping Tool Clone")
        info_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        info_title.setStyleSheet("color: #0078d7;")
        logo_layout.addWidget(info_title)
        logo_layout.addStretch()

        info_layout.addLayout(logo_layout)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("border-top: 1px solid #d0d0d0;")
        info_layout.addWidget(line)

        # Informationstext
        info_text = QLabel(
            "Erstellen Sie mit dem Snipping Tool Ausschnitte Ihres Bildschirms:\n\n"
            "1. Wählen Sie einen Aufnahmemodus\n"
            "2. Stellen Sie optional eine Verzögerung ein\n"
            "3. Klicken Sie auf 'Neu', um einen Screenshot zu erstellen\n"
            "4. Bearbeiten Sie den Screenshot mit den Zeichenwerkzeugen\n"
            "5. Speichern oder kopieren Sie das Ergebnis\n\n"
            "Tastenkürzel: Strg+Shift+S für schnellen Screenshot"
        )
        info_text.setFont(QFont("Segoe UI", 10))
        info_text.setStyleSheet("color: #505050;")
        info_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        info_layout.addWidget(info_text)

        # Hilfe-Button
        help_button = QPushButton("Hilfe erhalten")
        help_button.setStyleSheet("""
            background-color: #e0e0e0; 
            color: #505050;
        """)
        help_button.clicked.connect(self.show_help)
        info_layout.addWidget(help_button)

        # Füge Informationsbereich zum Hauptlayout hinzu
        main_layout.addWidget(info_widget)

        # Statusleiste
        self.statusBar().showMessage("Bereit. Drücken Sie Strg+Shift+S für einen schnellen Screenshot.")

        # Menü erstellen
        menubar = self.menuBar()

        # Datei-Menü
        file_menu = menubar.addMenu("Datei")

        new_action = QAction("Neu", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.take_screenshot)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        exit_action = QAction("Beenden", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Bearbeiten-Menü
        edit_menu = menubar.addMenu("Bearbeiten")

        copy_action = QAction("In Zwischenablage kopieren", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.copy_last_to_clipboard)
        edit_menu.addAction(copy_action)

        # Optionen-Menü
        options_menu = menubar.addMenu("Optionen")

        always_top_action = QAction("Immer im Vordergrund", self)
        always_top_action.setCheckable(True)
        always_top_action.triggered.connect(self.toggle_always_on_top)
        options_menu.addAction(always_top_action)

        # Hilfe-Menü
        help_menu = menubar.addMenu("Hilfe")

        help_action = QAction("Hilfe anzeigen", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)

        help_menu.addSeparator()

        about_action = QAction("Über", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Shortcut für Screenshot
        self.shortcut_snip = QShortcut(self)
        self.shortcut_snip.setKey(Qt.CTRL + Qt.SHIFT + Qt.Key_S)
        self.shortcut_snip.activated.connect(self.take_screenshot)

        # Letzte temporäre Datei speichern
        self.last_screenshot = None

    def create_icon(self):
        """Erstellt ein Icon für das Fenster"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_icon(painter, pixmap.rect())
        painter.end()
        return QIcon(pixmap)

    def draw_icon(self, painter, rect):
        """Zeichnet ein Snipping-Tool-Icon"""
        # Hintergrund
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#0078d7")))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 5, 5)

        # Schere
        pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pen)

        # Schere Griff
        painter.drawLine(
            int(rect.left() + rect.width() * 0.25),
            int(rect.top() + rect.height() * 0.6),
            int(rect.left() + rect.width() * 0.4),
            int(rect.top() + rect.height() * 0.8)
        )

        painter.drawLine(
            int(rect.left() + rect.width() * 0.6),
            int(rect.top() + rect.height() * 0.8),
            int(rect.left() + rect.width() * 0.75),
            int(rect.top() + rect.height() * 0.6)
        )

        # Schere Oberseite
        path = QPainterPath()
        path.moveTo(int(rect.left() + rect.width() * 0.25), int(rect.top() + rect.height() * 0.6))
        path.lineTo(int(rect.left() + rect.width() * 0.5), int(rect.top() + rect.height() * 0.35))
        path.lineTo(int(rect.left() + rect.width() * 0.75), int(rect.top() + rect.height() * 0.6))
        painter.drawPath(path)

        # Schere Kreise
        painter.drawEllipse(
            QPoint(int(rect.left() + rect.width() * 0.35), int(rect.top() + rect.height() * 0.65)),
            int(rect.width() * 0.06),
            int(rect.width() * 0.06)
        )

        painter.drawEllipse(
            QPoint(int(rect.left() + rect.width() * 0.65), int(rect.top() + rect.height() * 0.65)),
            int(rect.width() * 0.06),
            int(rect.width() * 0.06)
        )

    def take_screenshot(self):
        mode = self.mode_combo.currentText()
        delay = self.delay_spinner.value()

        # Status aktualisieren
        self.statusBar().showMessage(f"Erstelle Screenshot im Modus: {mode}...")

        # Bei Verzögerung: Fenster minimieren und Countdown anzeigen
        if delay > 0:
            self.showMinimized()

            # Countdown-Overlay anzeigen
            self.countdown = CountdownOverlay(delay)
            self.countdown.finished.connect(self.perform_screenshot)
            self.countdown.show()
        else:
            # Sofort Screenshot machen
            self.perform_screenshot()

    def perform_screenshot(self):
        # Temporäre Datei für Screenshot
        temp_file = tempfile.mktemp(suffix='.png')
        self.last_screenshot = temp_file

        # Basierend auf dem ausgewählten Modus den richtigen gnome-screenshot Befehl ausführen
        mode = self.mode_combo.currentText()

        if mode == "Rechteckiger Ausschnitt":
            subprocess.run(['gnome-screenshot', '-a', '-f', temp_file])
        elif mode == "Fenster-Ausschnitt":
            subprocess.run(['gnome-screenshot', '-w', '-f', temp_file])
        elif mode == "Vollbild-Ausschnitt":
            subprocess.run(['gnome-screenshot', '-f', temp_file])
        else:  # Freiform ist nicht direkt mit gnome-screenshot möglich, verwenden wir Rechteck
            subprocess.run(['gnome-screenshot', '-a', '-f', temp_file])

        # Prüfen, ob die Datei erzeugt wurde
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            self.open_editor(temp_file)
        else:
            self.statusBar().showMessage("Screenshot konnte nicht erstellt werden.")

        # Fenster wieder anzeigen
        self.showNormal()

    def open_editor(self, image_path):
        """Öffnet den Editor für den Screenshot"""
        self.editor = EditorWidget(image_path)
        self.editor.setWindowTitle("Screenshot bearbeiten")
        self.editor.setWindowIcon(self.windowIcon())
        self.editor.resize(1024, 768)  # Größeres Fenster
        self.editor.show()

    def copy_last_to_clipboard(self):
        """Kopiert den letzten Screenshot in die Zwischenablage"""
        if self.last_screenshot and os.path.exists(self.last_screenshot):
            try:
                subprocess.run(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i', self.last_screenshot])
                self.statusBar().showMessage("Screenshot in die Zwischenablage kopiert")
            except Exception as e:
                self.statusBar().showMessage(f"Fehler beim Kopieren in die Zwischenablage: {str(e)}")
        else:
            self.statusBar().showMessage("Kein Screenshot zum Kopieren verfügbar")

    def toggle_always_on_top(self, checked):
        """Setzt das Fenster immer im Vordergrund oder normal"""
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def show_help(self):
        """Zeigt die Hilfe an"""
        help_text = """
        <h2>Snipping Tool Clone - Hilfe</h2>
        <p>Mit diesem Tool können Sie Screenshots erstellen und bearbeiten.</p>

        <h3>Aufnahmemodi</h3>
        <ul>
            <li><b>Rechteckiger Ausschnitt:</b> Ziehen Sie ein Rechteck auf, um den Bereich auszuwählen.</li>
            <li><b>Freiform-Ausschnitt:</b> Zeichnen Sie eine beliebige Form, um den Bereich auszuwählen.</li>
            <li><b>Fenster-Ausschnitt:</b> Wählen Sie ein Fenster aus, um es zu erfassen.</li>
            <li><b>Vollbild-Ausschnitt:</b> Erfasst den gesamten Bildschirm.</li>
        </ul>

        <h3>Verzögerung</h3>
        <p>Stellen Sie eine Verzögerung ein, um Zeit zu haben, Menüs zu öffnen oder andere Vorbereitungen zu treffen, bevor der Screenshot erstellt wird.</p>

        <h3>Bearbeitungswerkzeuge</h3>
        <ul>
            <li><b>Stift:</b> Zeichnet mit einer soliden Linie.</li>
            <li><b>Marker:</b> Zeichnet mit einer halbtransparenten Linie.</li>
            <li><b>Radiergummi:</b> Entfernt Zeichnungen.</li>
            <li><b>Rechteck/Ellipse:</b> Zeichnet Formen.</li>
        </ul>

        <h3>Tastenkürzel</h3>
        <ul>
            <li><b>Strg+Shift+S:</b> Schneller Screenshot mit aktuellen Einstellungen</li>
            <li><b>Strg+N:</b> Neuer Screenshot</li>
            <li><b>Strg+C:</b> In Zwischenablage kopieren</li>
            <li><b>F1:</b> Hilfe anzeigen</li>
        </ul>
        """

        QMessageBox.information(self, "Hilfe", help_text)

    def show_about(self):
        """Zeigt Informationen über die Anwendung an"""
        about_text = """
        <h2>MS Snipping Tool Clone</h2>
        <p>Version 1.0</p>
        <p>Eine Nachbildung des Microsoft Snipping Tools für Linux</p>
        <p>Erstellt mit PyQt5 und gnome-screenshot</p>
        <p>© 2025 Tim Steegmüller</p>
        """

        QMessageBox.about(self, "Über MS Snipping Tool Clone", about_text)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modernes Look-and-Feel
    window = SnippingTool()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()