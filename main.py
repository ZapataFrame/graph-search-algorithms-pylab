"""Interfaz de escritorio: python main.py. No requiere conexión a Internet."""
import sys
from math import inf
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QAbstractItemView, QFrame, QSpinBox,
    QFileDialog, QMessageBox, QProgressDialog,
)
from graph_data import build_graph, load_graph
from algorithms import search, brute_force, ALGORITHMS, DESCRIPTIONS

from rendering import GraphCanvas, COLORS, FONT, load_font, render_slide, fmt, node_state, legend_text
from exporting import ExportJob

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.model = build_graph()
        self.original_model = self.model
        self.negative_model = None
        self.graph_name = 'Original'
        self.export_job = None
        negative_path = Path(__file__).parent / 'graphs/negative.json'
        self.negative_error = None
        if negative_path.exists():
            try:
                self.negative_model = load_graph(negative_path)
            except (ValueError, OSError) as error:
                self.negative_error = str(error)
        self.steps, self.index = [], 0
        self.click_source = True
        self.stream = None
        self.fast_mode = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.setWindowTitle('PyLab · cuaderno de grafos')
        self.resize(1500, 960)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        title = QLabel('PyLab / cuaderno de grafos')
        title.setObjectName('title')
        layout.addWidget(title)
        self.subtitle = QLabel(f'Diego Eduardo Zapata Aguilar   •   {self.model.graph.vcount()} nodos   /   '
                          f'{self.model.graph.ecount()} aristas   /   Grafo ponderado no dirigido')
        self.subtitle.setObjectName('muted')
        layout.addWidget(self.subtitle)
        actions = QHBoxLayout()
        self.graph_choice = QComboBox()
        self.graph_choice.addItems(['Original', 'Valores negativos · pendiente'])
        self.graph_choice.model().item(1).setEnabled(self.negative_model is not None)
        if self.negative_error:
            self.graph_choice.setItemText(1,'Variante JSON inválida')
            self.graph_choice.setToolTip(self.negative_error)
        if self.negative_model is not None:
            self.graph_choice.setItemText(1,'Valores negativos')
        actions.addWidget(QLabel('Grafo'))
        actions.addWidget(self.graph_choice)
        self.import_button = QPushButton('Importar variante JSON')
        self.import_button.clicked.connect(self.import_variant)
        actions.addWidget(self.import_button)
        actions.addStretch()
        self.image_button = QPushButton('Exportar imagen')
        self.image_button.clicked.connect(self.export_image)
        self.process_button = QPushButton('Guardar proceso')
        self.process_button.clicked.connect(self.export_process)
        for button in (self.image_button,self.process_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        controls = QHBoxLayout()
        self.source, self.target, self.algorithm = QComboBox(), QComboBox(), QComboBox()
        for combo in (self.source, self.target):
            combo.addItems([str(n) for n in self.model.nodes])
            combo.setMinimumWidth(82)
        self.source.setCurrentText('29')
        self.target.setCurrentText('13')
        self.algorithm.addItems(ALGORITHMS)
        self.algorithm.setMinimumWidth(220)
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
        self.legend_items = {}
        for state, label in [('unseen', 'Sin visitar'), ('frontier', 'Frontera'), ('visited', 'Visitado'),
                             ('current', 'Actual / arista'), ('path', 'Ruta final'), ('negative','Ciclo negativo')]:
            item = QLabel('  ' + label + '  ')
            item.setStyleSheet(f'background: {COLORS[state]}; color: #49453f; padding: 4px; border: 1px solid #d9d3ca; border-radius: 5px; font-size: 11px;')
            self.legend_items[state] = item
            legend.addWidget(item)
        left_layout.addLayout(legend)
        left_layout.addWidget(QLabel('Clic alternado: origen y destino. Anillo verde: origen · rosa: destino.'))
        split.addWidget(left)
        right = QWidget()
        right.setMinimumWidth(390)
        sidebar = QVBoxLayout(right)
        sidebar.setContentsMargins(12, 0, 0, 0)
        sidebar.addWidget(QLabel('ESTADO DE LA BÚSQUEDA'))
        self.stats = QLabel()
        self.stats.setObjectName('stats')
        sidebar.addWidget(self.stats)
        self.table = QTableWidget(len(self.model.nodes), 6)
        self.table.setHorizontalHeaderLabels(['Nodo','g','h','f','Padre','Estado'])
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
        split.setSizes([1050,410])
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
        self.graph_choice.currentIndexChanged.connect(self.select_graph)
        self.prepare()
        if self.negative_error:
            self.statusBar().showMessage("Variante no cargada: " + self.negative_error)

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
        self.table.setColumnHidden(2, algorithm != 'A*')
        self.table.setColumnHidden(3, algorithm != 'A*')
        self.table.horizontalHeaderItem(1).setText('Rama g' if brute else 'g')
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

    def closeEvent(self,event):
        self.pause()
        if self.export_job is not None:
            self.export_job.cancel()
        event.accept()

    def import_variant(self):
        path,_=QFileDialog.getOpenFileName(self,'Seleccionar variante ponderada','','Grafos JSON (*.json)')
        if not path: return
        try:
            model=load_graph(path)
        except (ValueError,OSError) as error:
            QMessageBox.warning(self,'Grafo inválido',str(error))
            return
        self.negative_model=model
        self.graph_choice.setItemText(1,'Variante ponderada')
        self.graph_choice.model().item(1).setEnabled(True)
        if self.graph_choice.currentIndex()==1:
            self.select_graph(1)
        else:
            self.graph_choice.setCurrentIndex(1)

    def select_graph(self,index):
        if index==1 and self.negative_model is None: return
        self.pause()
        self.model=self.original_model if index==0 else self.negative_model
        self.graph_name=self.graph_choice.currentText()
        self.canvas.model=self.model
        old_source,old_target=self.source.currentText(),self.target.currentText()
        for combo,old in ((self.source,old_source),(self.target,old_target)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems([str(n) for n in self.model.nodes])
            if old in [str(n) for n in self.model.nodes]: combo.setCurrentText(old)
            combo.blockSignals(False)
        self.algorithm.blockSignals(True)
        for i,name in enumerate(ALGORITHMS):
            self.algorithm.model().item(i).setEnabled(not(self.model.has_negative_weights and name in ('Dijkstra','A*')))
        if self.model.has_negative_weights and self.algorithm.currentText() in ('Dijkstra','A*'):
            self.algorithm.setCurrentText('Bellman–Ford')
        self.algorithm.blockSignals(False)
        kind='dirigido' if self.model.graph.is_directed() else 'no dirigido'
        self.subtitle.setText(f'Diego Eduardo Zapata Aguilar · {len(self.model.nodes)} nodos · {self.model.graph.ecount()} aristas · {kind}')
        self.table.setRowCount(len(self.model.nodes))
        self.prepare()

    def export_image(self):
        self.pause()
        path,_=QFileDialog.getSaveFileName(self,'Exportar paso actual',f'paso-{self.index+1:06d}.png','Imagen PNG (*.png)')
        if not path: return
        if not path.lower().endswith('.png'): path+='.png'
        try:
            step=self.steps[self.index]
            total=str(len(self.steps))+('+' if self.stream is not None else '')
            image=render_slide(self.model,step,int(self.source.currentText()),int(self.target.currentText()),
                               self.algorithm.currentText(),self.graph_name,self.index,total)
            if not image.save(path,'PNG'): raise OSError('No se pudo guardar la imagen.')
            self.statusBar().showMessage(f'Imagen guardada: {path}',8000)
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,'Error al exportar',str(error))

    def export_process(self):
        self.pause()
        folder=QFileDialog.getExistingDirectory(self,'Guardar carpeta del proceso')
        if not folder: return
        output=Path(folder)/('pylab-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:6])
        a,b=int(self.source.currentText()),int(self.target.currentText())
        algorithm=self.algorithm.currentText()
        if algorithm==ALGORITHMS[3]:
            iterator=brute_force(self.model,a,b,self.limit.value())
            total=f'≤ {self.limit.value()+1}'
            maximum=self.limit.value()+1
        else:
            iterator=self.steps
            total=maximum=len(self.steps)
        self.export_dialog=QProgressDialog('Guardando todos los pasos como PNG…','Cancelar',0,maximum,self)
        self.export_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.export_dialog.setMinimumDuration(0)
        self.export_dialog.setAutoClose(False)
        self.export_dialog.setAutoReset(False)
        job=ExportJob(output,iterator,self.model,a,b,algorithm,self.graph_name,total,self)
        self.export_job=job
        job.progress.connect(self.export_dialog.setValue)
        job.finished.connect(self.export_finished)
        job.failed.connect(self.export_failed)
        self.export_dialog.canceled.connect(job.cancel)
        self.export_dialog.show()
        QTimer.singleShot(0,job.start)

    def export_finished(self,folder):
        self.export_dialog.close()
        count=self.export_job.count
        self.statusBar().showMessage(f'{count} imágenes guardadas en {folder}',15000)
        self.export_job.deleteLater()
        self.export_job=None

    def export_failed(self,message):
        self.export_dialog.close()
        QMessageBox.warning(self,'Error al guardar el proceso',message)
        self.export_job.deleteLater()
        self.export_job=None

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
        used=dict(legend_text(step,self.model))
        for key,item in self.legend_items.items():
            item.setVisible(key in used)
            if key in used: item.setText('  '+used[key]+'  ')
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
            state = 'Ciclo −' if node in step.negative_nodes else ('Provisional' if step.limited else 'Ruta') if node in step.path_nodes else 'Actual' if node == step.current else \
                    'Rama' if node in step.branch_nodes else 'Visitado' if node in step.visited else 'Frontera' if node in step.frontier else 'Pendiente'
            h = step.heuristic.get(node) if step.heuristic is not None else None
            values = (str(node), fmt(cost), f'{h:.2f}' if h is not None else '—',
                      fmt(cost+h) if h is not None else '—', parent, state)
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QColor(COLORS[node_state(step,node)]))
                self.table.setItem(row, col, item)

STYLE = """
QWidget { background: #ffffff; color: #393631; font-family: "Excalifont"; font-size: 14px; }
QLabel#title { font-size: 29px; }
QLabel#muted { color: #817b72; font-size: 12px; }
QLabel#panelHeading { font-size: 24px; padding: 8px; }
QLabel#stats { background: #eef5fa; padding: 10px; border-radius: 8px; font-size: 12px; }
QLabel#message { background: #fff5e5; padding: 12px; border: 1px solid #ead7b4; border-radius: 9px; }
QPushButton, QComboBox, QSpinBox { background: #faf9f6; border: 1px solid #aaa399; border-radius: 8px; padding: 8px 11px; }
QPushButton:hover { background: #eef4f9; border-color: #817b71; }
QPushButton:disabled { color: #b8b2a9; border-color: #e3ded6; }
QPushButton#primary { background: #dff0e4; border: 1px solid #82ab90; }
QComboBox::drop-down { border: none; width: 20px; }
QTableWidget, QListWidget { background: #ffffff; border: 1px solid #ddd6cc; border-radius: 8px; gridline-color: #ebe6de; font-size: 12px; }
QHeaderView::section { background: #f6f3ed; padding: 7px 3px; border: none; font-size: 12px; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #eee8df; }
QListWidget::item:selected { background: #f0e6fc; color: #393631; }
QSlider::groove:horizontal { background: #ebe5dd; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal { background: #c5dccd; width: 17px; margin: -5px 0; border: 1px solid #859d8d; border-radius: 8px; }
QSplitter::handle { background: #e8e3db; width: 1px; }
QToolTip { background: #fff5e5; color: #393631; padding: 6px; border: 1px solid #d7c6a9; }
"""

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    load_font()
    app.setFont(QFont(FONT,11))
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
