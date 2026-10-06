"""Interfaz de escritorio: python main.py. No requiere conexión a Internet."""
import sys
from math import inf
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QAbstractItemView, QFrame, QSizePolicy, QSpinBox,
)
from graph_data import build_graph, POSITIONS
from algorithms import search, brute_force, ALGORITHMS, DESCRIPTIONS

BG = '#0c1322'
COLORS = {'unseen': '#334259', 'frontier': '#9178ee', 'visited': '#268fbd',
          'current': '#ffb454', 'path': '#40d9ac', 'edge': '#52627a'}

class GraphCanvas(QWidget):
    def __init__(self, model, choose):
        super().__init__()
        self.model, self.choose = model, choose
        self.step = None
        self.source, self.target = 29, 13
        self.points = {}
        self.setMinimumSize(640, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(BG))
        scale = min((self.width() - 100) / 1387, (self.height() - 110) / 797)
        ox, oy = (self.width() - 1387 * scale) / 2, (self.height() - 797 * scale) / 2
        self.points = {n: QPointF(ox + x * scale, oy + y * scale) for n, (x, y) in POSITIONS.items()}
        s = self.step
        route = set(s.path_edges) if s else set()
        branch = set(s.branch_edges) if s else set()
        p.setFont(QFont('Sans Serif', 9))
        labels = []
        for edge in self.model.graph.es:
            a, b = (self.model.nodes[i] for i in edge.tuple)
            start, end = self.points[a], self.points[b]
            dx, dy = end.x() - start.x(), end.y() - start.y()
            # Separar las aristas paralelas, conservando la identidad de cada una.
            bend = (30 if edge['weight'] == 16 else -30) * scale if {a, b} == {12, 16} else 0
            length = max((dx * dx + dy * dy) ** 0.5, 1)
            center = (start + end) / 2 + QPointF(-dy / length * bend, dx / length * bend)
            active = s and edge.index == s.active_edge
            color = COLORS['path'] if edge.index in route else COLORS['current'] if active else COLORS['frontier'] if edge.index in branch else COLORS['edge']
            p.setPen(QPen(QColor(color), 3.5 if edge.index in route or edge.index in branch or active else 1.25))
            path = QPainterPath(start)
            if bend:
                path.quadTo(center + (center - (start + end) / 2), end)
            else:
                path.lineTo(end)
            p.drawPath(path)
            # Las etiquetas se pintan después de todas las líneas.
            if {a, b} == {7, 1}:
                center = start + (end - start) * (0.38 if a == 7 else 0.62)
            elif {a, b} == {6, 9}:
                center += QPointF(15, 0)
            labels.append((center, str(edge['weight']), color, active or edge.index in route))
        for center, label, color, emphasized in labels:
            width = max(22, p.fontMetrics().horizontalAdvance(label) + 12)
            box = QRectF(center.x() - width / 2, center.y() - 10, width, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor('#142034'))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QColor(color if emphasized else '#c6d2e3'))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        radius = max(15, min(22, scale * 23))
        for node, point in self.points.items():
            state = 'unseen'
            if s:
                if node in s.frontier: state = 'frontier'
                if node in s.visited: state = 'visited'
                if node in s.branch_nodes: state = 'frontier'
                if node == s.current: state = 'current'
                if node in s.path_nodes: state = 'path'
            color = QColor(COLORS[state])
            if node in (self.source, self.target):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor('#40d9ac' if node == self.source else '#f28ca9'), 2))
                p.drawEllipse(point, radius + 5, radius + 5)
            p.setPen(QPen(color.lighter(130), 1.5))
            p.setBrush(color)
            p.drawEllipse(point, radius, radius)
            p.setFont(QFont('Sans Serif', 10, QFont.Weight.Bold))
            p.setPen(QColor('#0c1322' if state in ('current', 'path') else '#ffffff'))
            p.drawText(QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2),
                       Qt.AlignmentFlag.AlignCenter, str(node))
            if s and s.distances[node] != inf:
                label = f'd={s.distances[node]:g}'
                p.setFont(QFont('Sans Serif', 8))
                width = p.fontMetrics().horizontalAdvance(label) + 10
                box = QRectF(point.x() - width / 2, point.y() + radius + 6, width, 17)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(BG))
                p.drawRoundedRect(box, 4, 4)
                p.setPen(QColor('#e1e9f5'))
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, label)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position()
        for node, center in self.points.items():
            if (center.x() - point.x()) ** 2 + (center.y() - point.y()) ** 2 < 28 ** 2:
                self.choose(node)
                break

    def mouseMoveEvent(self, event):
        for node, center in self.points.items():
            if (center.x() - event.position().x()) ** 2 + (center.y() - event.position().y()) ** 2 < 26 ** 2:
                cost = self.step.distances[node] if self.step else inf
                text = '∞' if cost == inf else f'{cost:g}'
                edges = ', '.join(f'{n} (peso {w})' for n, w, _ in self.model.adjacency[node])
                self.setToolTip(f'Nodo {node} · distancia {text}\nVecinos: {edges}')
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        self.setToolTip('')
        self.setCursor(Qt.CursorShape.ArrowCursor)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = build_graph()
        self.steps, self.index = [], 0
        self.click_source = True
        self.stream = None
        self.fast_mode = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.setWindowTitle('Graph Studio · Dijkstra | Diego Eduardo Zapata Aguilar')
        self.resize(1500, 960)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        title = QLabel('GRAPH STUDIO   /   Laboratorio de rutas')
        title.setObjectName('title')
        layout.addWidget(title)
        subtitle = QLabel(f'Diego Eduardo Zapata Aguilar   •   {self.model.graph.vcount()} nodos   /   '
                          f'{self.model.graph.ecount()} aristas   /   Grafo ponderado no dirigido')
        subtitle.setObjectName('muted')
        layout.addWidget(subtitle)
        controls = QHBoxLayout()
        self.source, self.target, self.algorithm = QComboBox(), QComboBox(), QComboBox()
        for combo in (self.source, self.target):
            combo.addItems([str(n) for n in self.model.nodes])
            combo.setMinimumWidth(82)
        self.source.setCurrentText('29')
        self.target.setCurrentText('13')
        self.algorithm.addItems(ALGORITHMS)
        self.algorithm.setMinimumWidth(190)
        for label, combo in [('Origen A', self.source), ('Destino B', self.target), ('Algoritmo', self.algorithm)]:
            controls.addWidget(QLabel(label))
            controls.addWidget(combo)
        swap = QPushButton('⇄ Intercambiar')
        swap.clicked.connect(self.swap)
        controls.addWidget(swap)
        controls.addStretch()
        self.description = QLabel()
        layout.addLayout(controls)
        explanation = QHBoxLayout()
        self.description.setWordWrap(True)
        explanation.addWidget(self.description, 1)
        self.limit_label = QLabel('Límite fuerza bruta (pasos)')
        self.limit = QSpinBox()
        self.limit.setRange(100, 100000)
        self.limit.setSingleStep(1000)
        self.limit.setValue(10000)
        self.limit.setToolTip('Un corte por límite es provisional. Cada cambio inicia una búsqueda nueva.')
        explanation.addWidget(self.limit_label)
        explanation.addWidget(self.limit)
        layout.addLayout(explanation)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = GraphCanvas(self.model, self.pick_node)
        left_layout.addWidget(self.canvas, 1)
        legend = QHBoxLayout()
        for state, label in [('unseen', 'Sin visitar'), ('frontier', 'Frontera'), ('visited', 'Visitado'),
                             ('current', 'Actual / arista examinada'), ('path', 'Ruta final')]:
            item = QLabel('● ' + label)
            legend_color = '#92a7c4' if state == 'unseen' else COLORS[state]
            item.setStyleSheet(f'color: {legend_color}; font-size: 11px;')
            if state == 'path':
                self.route_legend = item
            legend.addWidget(item)
        left_layout.addLayout(legend)
        left_layout.addWidget(QLabel('Clic alternado: origen y destino. Anillo verde: origen · rosa: destino.'))
        split.addWidget(left)
        right = QWidget()
        right.setMinimumWidth(310)
        sidebar = QVBoxLayout(right)
        sidebar.setContentsMargins(12, 0, 0, 0)
        sidebar.addWidget(QLabel('ESTADO DE LA BÚSQUEDA'))
        self.stats = QLabel()
        self.stats.setObjectName('stats')
        sidebar.addWidget(self.stats)
        self.table = QTableWidget(len(self.model.nodes), 4)
        self.table.setHorizontalHeaderLabels(['Nodo', 'Costo', 'Padre', 'Estado'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        sidebar.addWidget(self.table, 3)
        sidebar.addWidget(QLabel('PASOS · selecciona uno para volver a él'))
        self.history = QListWidget()
        self.history.setWordWrap(True)
        self.history.currentRowChanged.connect(self.jump)
        sidebar.addWidget(self.history, 2)
        split.addWidget(right)
        split.setSizes([1080, 350])
        layout.addWidget(split, 1)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(54)
        self.message.setObjectName('message')
        layout.addWidget(self.message)
        playback = QHBoxLayout()
        self.reset = QPushButton('↺ Reiniciar')
        self.back = QPushButton('◀ Anterior')
        self.play = QPushButton('▶ Reproducir')
        self.play.setObjectName('primary')
        self.next = QPushButton('Siguiente ▶')
        self.end = QPushButton('Ver resultado')
        self.reset.clicked.connect(self.restart)
        self.back.clicked.connect(lambda: self.navigate(self.index - 1))
        self.play.clicked.connect(self.toggle)
        self.next.clicked.connect(lambda: self.navigate(self.index + 1))
        self.end.clicked.connect(self.reach_end)
        for button in (self.reset, self.back, self.play, self.next, self.end):
            playback.addWidget(button)
        playback.addStretch()
        playback.addWidget(QLabel('Velocidad'))
        self.speed = QComboBox()
        for label, ms in [('0.5×', 1600), ('1×', 800), ('2×', 400), ('4×', 200)]:
            self.speed.addItem(label, ms)
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(lambda: self.timer.setInterval(self.speed.currentData()))
        playback.addWidget(self.speed)
        self.counter = QLabel()
        playback.addWidget(self.counter)
        layout.addLayout(playback)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.valueChanged.connect(self.navigate)
        layout.addWidget(self.timeline)
        for combo in (self.source, self.target, self.algorithm):
            combo.currentIndexChanged.connect(self.prepare)
        self.limit.valueChanged.connect(self.prepare)
        self.prepare()

    def prepare(self):
        self.pause()
        a, b = int(self.source.currentText()), int(self.target.currentText())
        if self.stream is not None:
            self.stream.close()
        algorithm = self.algorithm.currentText()
        brute = algorithm == ALGORITHMS[3]
        self.stream = brute_force(self.model, a, b, self.limit.value()) if brute else None
        self.steps = [next(self.stream)] if brute else search(self.model, a, b, algorithm)
        self.canvas.source, self.canvas.target = a, b
        self.description.setText(DESCRIPTIONS[algorithm])
        self.limit.setVisible(brute)
        self.limit_label.setVisible(brute)
        self.end.setText('Calcular resultado' if brute else 'Ver resultado')
        self.table.horizontalHeaderItem(1).setText('Costo rama' if brute else 'Costo')
        self.table.setToolTip('En fuerza bruta, los costos y padres pertenecen a la rama mostrada; '
                              'visitado significa visto alguna vez, no descartado definitivamente.')
        self.history.blockSignals(True)
        self.history.clear()
        self.history.addItems([f'{i + 1:03d}  {s.message}' for i, s in enumerate(self.steps)])
        self.history.blockSignals(False)
        self.timeline.blockSignals(True)
        self.timeline.setRange(0, len(self.steps) - 1)
        self.timeline.blockSignals(False)
        self.show_step(0)

    def swap(self):
        a, b = self.source.currentText(), self.target.currentText()
        self.source.blockSignals(True)
        self.source.setCurrentText(b)
        self.source.blockSignals(False)
        self.target.blockSignals(True)
        self.target.setCurrentText(a)
        self.target.blockSignals(False)
        self.prepare()

    def pick_node(self, node):
        (self.source if self.click_source else self.target).setCurrentText(str(node))
        self.click_source = not self.click_source

    def pause(self):
        self.timer.stop()
        self.fast_mode = False
        if hasattr(self, 'play'):
            self.play.setText('▶ Reproducir')

    def restart(self):
        # Fuerza bruta también reinicia el generador y su presupuesto.
        if self.algorithm.currentText() == ALGORITHMS[3]:
            self.prepare()
        else:
            self.navigate(0)

    def append_step(self):
        if self.stream is None:
            return False
        try:
            step = next(self.stream)
        except StopIteration:
            self.stream = None
            return False
        self.steps.append(step)
        self.history.blockSignals(True)
        self.history.addItem(f'{len(self.steps):03d}  {step.message}')
        self.history.blockSignals(False)
        self.timeline.blockSignals(True)
        self.timeline.setMaximum(len(self.steps) - 1)
        self.timeline.blockSignals(False)
        if step.done:
            self.stream.close()
            self.stream = None
        return True

    def reach_end(self):
        if self.stream is None:
            self.navigate(len(self.steps) - 1)
        else:
            self.fast_mode = True
            self.timer.start(1)
            self.play.setText('Ⅱ Pausar')

    def toggle(self):
        if self.timer.isActive():
            self.pause()
        else:
            if self.index == len(self.steps) - 1 and self.stream is None:
                self.restart()
            self.timer.start(self.speed.currentData())
            self.play.setText('Ⅱ Pausar')

    def advance(self):
        # Los lotes pequeños devuelven el control a Qt: se puede pausar o cambiar
        # los inputs durante la enumeración, sin bloquear la ventana.
        if self.fast_mode:
            for _ in range(100):
                if not self.append_step():
                    break
            self.show_step(len(self.steps) - 1)
        else:
            if self.index == len(self.steps) - 1:
                self.append_step()
            self.show_step(self.index + 1)
        if self.index == len(self.steps) - 1 and self.stream is None:
            self.pause()

    def jump(self, row):
        if row >= 0:
            self.navigate(row)

    def navigate(self, index):
        self.pause()
        if index >= len(self.steps) and self.stream is not None:
            self.append_step()
        self.show_step(index)

    def show_step(self, index):
        self.index = max(0, min(index, len(self.steps) - 1))
        step = self.steps[self.index]
        self.route_legend.setText('● Mejor provisional' if step.limited else '● Ruta final')
        self.canvas.step = step
        self.canvas.update()
        self.message.setText(step.message)
        suffix = '+' if self.stream is not None else ''
        self.counter.setText(f'Paso {self.index + 1} / {len(self.steps)}{suffix}')
        self.stats.setText(f'Actual: {step.current if step.current is not None else "—"}    '
                           f'Visitados: {len(step.visited)}    Frontera: {len(step.frontier)}'
                           + (f'\nCaminos completos: {step.candidates}'
                              if self.algorithm.currentText() == ALGORITHMS[3] else ''))
        self.timeline.blockSignals(True)
        self.timeline.setValue(self.index)
        self.timeline.blockSignals(False)
        self.history.blockSignals(True)
        self.history.setCurrentRow(self.index)
        self.history.scrollToItem(self.history.currentItem())
        self.history.blockSignals(False)
        self.back.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < len(self.steps) - 1 or self.stream is not None)
        for row, node in enumerate(self.model.nodes):
            cost = step.distances[node]
            parent = str(step.parents[node][0]) if node in step.parents else '—'
            state = ('Provisional' if step.limited else 'Ruta') if node in step.path_nodes else 'Actual' if node == step.current else \
                    'Rama' if node in step.branch_nodes else 'Visitado' if node in step.visited else 'Frontera' if node in step.frontier else 'Pendiente'
            for col, text in enumerate((str(node), '∞' if cost == inf else f'{cost:g}', parent, state)):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

STYLE = '''
QWidget { background: #101a2b; color: #dae4f4; font-family: "Sans Serif"; font-size: 12px; }
QLabel#title { font-size: 25px; font-weight: bold; color: #f1f6ff; }
QLabel#muted { color: #92a7c4; }
QLabel#stats { background: #19283e; padding: 12px; border-radius: 8px; color: #7dd9f5; }
QLabel#message { background: #19283e; padding: 12px; border-left: 3px solid #ffb454; border-radius: 6px; font-size: 14px; }
QPushButton, QComboBox { background: #22324b; border: 1px solid #354864; border-radius: 7px; padding: 9px 12px; }
QPushButton:hover { background: #314867; }
QPushButton:disabled { color: #607089; background: #172338; }
QPushButton#primary { background: #40d9ac; color: #0b1a20; font-weight: bold; }
QPushButton#primary:hover { background: #72e9c4; }
QComboBox::drop-down { border: none; width: 22px; }
QTableWidget, QListWidget { background: #0c1322; border: 1px solid #263852; border-radius: 6px; gridline-color: #1e2d44; }
QHeaderView::section { background: #22324b; color: #bcd0ec; padding: 7px; border: none; }
QListWidget::item { padding: 8px; border-bottom: 1px solid #1b2a40; }
QListWidget::item:selected { background: #2b4563; color: #ffffff; }
QSlider::groove:horizontal { background: #2b3b55; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #40d9ac; width: 16px; margin: -5px 0; border-radius: 8px; }
QSplitter::handle { background: #263852; width: 2px; }
QToolTip { background: #22324b; color: #ffffff; padding: 6px; border: 1px solid #40d9ac; }
'''

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    # Captura reproducible para revisión visual o documentación.
    if '--screenshot' in sys.argv:
        i = sys.argv.index('--screenshot')
        output = Path(sys.argv[i + 1])
        def capture():
            window.navigate(len(window.steps) - 1)
            app.processEvents()
            if not window.grab().save(str(output)):
                raise RuntimeError(f'No se pudo guardar {output}')
            app.quit()
        QTimer.singleShot(250, capture)
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
