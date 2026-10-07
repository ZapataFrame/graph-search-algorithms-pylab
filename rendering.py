"""Dibujo determinista de pizarra y exportaciones PNG independientes del tamaño UI."""
from math import cos, sin, pi, hypot, inf
from pathlib import Path
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPen, QFont, QPainterPath, QPainter, QImage, QFontDatabase
from PyQt6.QtWidgets import QWidget, QSizePolicy

FONT = 'Excalifont'
COLORS = {'unseen': '#ffffff', 'frontier': '#e9ddfb', 'visited': '#d8ebfb',
          'current': '#ffe4bd', 'path': '#d8f1df', 'negative': '#ffd9de', 'edge': '#9d9b97'}
INK = '#363532'
LABELS = {'unseen': 'Sin visitar', 'frontier': 'Frontera / rama', 'visited': 'Visitado',
          'current': 'Actual / arista', 'path': 'Ruta', 'negative': 'Ciclo negativo'}


def load_font():
    path = Path(__file__).parent / 'assets/fonts/Excalifont-Latin.woff2'
    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        raise RuntimeError(f'No se pudo cargar la fuente incluida: {path}')
    return QFontDatabase.applicationFontFamilies(font_id)[0]


def fmt(number):
    if number == inf: return '∞'
    if number == -inf: return '−∞'
    return f'{number:g}'


def sketch_circle(center, radius, seed):
    path = QPainterPath()
    for i in range(81):
        angle = 2*pi*i/80
        r = radius + 0.6*sin(3*angle+seed) + 0.35*cos(5*angle+seed*0.7)
        point = center + QPointF(r*cos(angle), r*sin(angle)*0.98)
        if i == 0: path.moveTo(point)
        else: path.lineTo(point)
    path.closeSubpath()
    return path


def node_state(step, node):
    state = 'unseen'
    if step:
        if node in step.frontier: state = 'frontier'
        if node in step.visited: state = 'visited'
        if node in step.branch_nodes: state = 'frontier'
        if node == step.current: state = 'current'
        if node in step.path_nodes: state = 'path'
        if node in step.negative_nodes: state = 'negative'
    return state


def draw_graph(p, rect, model, step, source, target):
    """Centra y ajusta por extensión de posiciones; deja espacio para anillos/costos."""
    positions = model.positions
    xs, ys = [x for x, _ in positions.values()], [y for _, y in positions.values()]
    width, height = max(max(xs)-min(xs), 1), max(max(ys)-min(ys), 1)
    scale = min((rect.width()-120)/width, (rect.height()-120)/height)
    scale = max(scale, 0.01)
    ox = rect.center().x() - (min(xs)+max(xs))*scale/2
    oy = rect.center().y() - (min(ys)+max(ys))*scale/2
    points = {n: QPointF(ox+x*scale, oy+y*scale) for n,(x,y) in positions.items()}
    radius = max(16, min(25, 24*scale))
    routes = set(step.path_edges) if step else set()
    branches = set(step.branch_edges) if step else set()
    groups = {}
    for edge in model.graph.es:
        key = tuple(sorted(edge.tuple))
        groups.setdefault(key, []).append(edge.index)
    labels = []
    p.save()
    p.setClipRect(rect)
    for edge in model.graph.es:
        u, v = (model.nodes[i] for i in edge.tuple)
        start, end = points[u], points[v]
        dx, dy = end.x()-start.x(), end.y()-start.y()
        length = max(hypot(dx,dy), 1)
        ids = groups[tuple(sorted(edge.tuple))]
        offset = (ids.index(edge.index)-(len(ids)-1)/2)*48
        if u > v: offset = -offset
        perpendicular = QPointF(-dy/length, dx/length)
        center = (start+end)/2 + perpendicular*offset
        active = step and step.active_edge == edge.index
        highlight = active or edge.index in routes or edge.index in branches
        stroke = '#35936a' if edge.index in routes else '#c77d2b' if active else '#9473bd' if edge.index in branches else '#aaa59e'
        p.setPen(QPen(QColor(stroke), 2.8 if highlight else 1.25, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        curve = QPainterPath(start)
        if u == v:
            curve.cubicTo(start+QPointF(-50,-65), start+QPointF(55,-65), start)
            center = start+QPointF(0,-48)
        else:
            control = center+(center-(start+end)/2) + perpendicular*(0.7*sin(edge.index))
            curve.quadTo(control,end)
        p.drawPath(curve)
        if model.graph.is_directed():
            # Punta a la entrada del círculo, siguiendo la tangente de la curva.
            percent = max(0.55, 1-(radius+3)/length)
            tip = curve.pointAtPercent(percent)
            before = curve.pointAtPercent(max(0,percent-0.03))
            vector = tip-before
            vl = max(hypot(vector.x(),vector.y()),1)
            unit = vector/vl
            normal = QPointF(-unit.y(),unit.x())
            p.drawLine(tip,tip-unit*10+normal*5)
            p.drawLine(tip,tip-unit*10-normal*5)
        if {u,v} == {7,1}:
            center = start+(end-start)*(0.38 if u==7 else 0.62)
        elif {u,v} == {6,9}:
            center += QPointF(15,0)
        labels.append((center,fmt(edge['weight']),highlight,stroke))
    p.setFont(QFont(FONT,11))
    for center, label, highlight, stroke in labels:
        w=p.fontMetrics().horizontalAdvance(label)+10
        box=QRectF(center.x()-w/2,center.y()-11,w,22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#fff3df' if highlight else '#ffffff'))
        p.drawRoundedRect(box,4,4)
        p.setPen(QColor(stroke if highlight else '#5a5752'))
        p.drawText(box,Qt.AlignmentFlag.AlignCenter,label)
    for node,center in points.items():
        state=node_state(step,node)
        if node in (source,target):
            p.setPen(QPen(QColor('#579577' if node==source else '#b77e9e'),1.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(sketch_circle(center,radius+5,node+1))
        p.setPen(QPen(QColor(INK),1.5))
        p.setBrush(QColor(COLORS[state]))
        p.drawPath(sketch_circle(center,radius,node))
        # Segundo trazo corto, reproducible, evita parpadeo al avanzar.
        if state!='unseen':
            p.setPen(QPen(QColor('#77716a'),0.55))
            arc=QPainterPath()
            arc.moveTo(center+QPointF(radius,0))
            arc.arcTo(QRectF(center.x()-radius-0.9,center.y()-radius-0.3,2*radius+1,2*radius),0,80)
            p.drawPath(arc)
        p.setFont(QFont(FONT,13 if len(str(node))<3 else 11))
        p.setPen(QColor(INK))
        p.drawText(QRectF(center.x()-radius,center.y()-radius,2*radius,2*radius),Qt.AlignmentFlag.AlignCenter,str(node))
        if step and step.distances[node]!=inf:
            p.setFont(QFont(FONT,9))
            label='g='+fmt(step.distances[node])
            w=p.fontMetrics().horizontalAdvance(label)+8
            box=QRectF(center.x()-w/2,center.y()+radius+6,w,19)
            p.fillRect(box,QColor('#ffffff'))
            p.drawText(box,Qt.AlignmentFlag.AlignCenter,label)
    p.restore()
    return points


def legend_text(step=None):
    path_label='Mejor provisional' if step and step.limited else 'Ruta encontrada'
    return [('unseen','Sin visitar'),('frontier','Frontera / rama'),('visited','Visitado'),
            ('current','Actual / arista'),('path',path_label),('negative','Ciclo negativo')]


def draw_legend(p,rect,step=None):
    p.setFont(QFont(FONT,11))
    cursor=rect.left()
    for key,label in legend_text(step):
        p.setPen(QPen(QColor('#66625c'),1))
        p.setBrush(QColor(COLORS[key]))
        p.drawRoundedRect(QRectF(cursor,rect.center().y()-7,14,14),3,3)
        p.setPen(QColor(INK))
        p.drawText(QRectF(cursor+22,rect.top(),p.fontMetrics().horizontalAdvance(label)+8,rect.height()),
                   Qt.AlignmentFlag.AlignVCenter,label)
        cursor += p.fontMetrics().horizontalAdvance(label)+46


def render_slide(model,step,source,target,algorithm,graph_name,index,total,presentation=True):
    image=QImage(1800,1120,QImage.Format.Format_ARGB32)
    image.fill(QColor('white'))
    p=QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setFont(QFont(FONT,25))
    p.setPen(QColor(INK))
    p.drawText(QRectF(48,25,1650,55),Qt.AlignmentFlag.AlignLeft,algorithm+' / '+graph_name)
    p.setFont(QFont(FONT,13))
    p.drawText(QRectF(48,85,1650,35),f'Origen {source}   →   Destino {target}     ·     Paso {index+1} / {total}')
    graph_rect=QRectF(30,140,1270 if presentation else 1740,840)
    draw_graph(p,graph_rect,model,step,source,target)
    if presentation:
        panel=QRectF(1330,145,425,840)
        p.setPen(QPen(QColor('#c2bab0'),1.3))
        p.setBrush(QColor('#faf8f4'))
        p.drawRoundedRect(panel,16,16)
        p.setPen(QColor(INK))
        p.setFont(QFont(FONT,20))
        p.drawText(QRectF(1355,175,370,45),'¿Qué ocurre aquí?')
        p.setFont(QFont(FONT,16))
        p.drawText(QRectF(1355,240,365,330),Qt.TextFlag.TextWordWrap,step.message)
        p.setFont(QFont(FONT,13))
        text=f'Actual: {step.current if step.current is not None else "—"}\nVistos: {len(step.visited)} · Frontera: {len(step.frontier)}'
        if step.pass_number: text+=f'\nPasada: {step.pass_number}'
        if step.heuristic and step.current is not None:
            n=step.current
            text+=f'\ng = {fmt(step.distances[n])}\nh = {step.heuristic[n]:.3f}\nf = {step.distances[n]+step.heuristic[n]:.3f}'
        if step.limited: text+='\nResultado provisional: búsqueda incompleta.'
        if step.negative_nodes: text+='\nRojo: costo no finito por ciclo negativo.'
        p.drawText(QRectF(1355,590,365,210),Qt.TextFlag.TextWordWrap,text)
        p.setFont(QFont(FONT,11))
        p.drawText(QRectF(1355,850,365,90),Qt.TextFlag.TextWordWrap,
                   'g: costo acumulado · h: estimación restante · f = g + h\nAnillo verde: origen · anillo rosa: destino')
    draw_legend(p,QRectF(55,1030,1690,50),step)
    p.end()
    return image


class GraphCanvas(QWidget):
    def __init__(self,model,choose):
        super().__init__()
        self.model,self.choose=model,choose
        self.step=None
        self.source,self.target=29,13
        self.points={}
        self.setMinimumSize(620,420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('white'))
        self.points=draw_graph(p,QRectF(self.rect()),self.model,self.step,self.source,self.target)
        p.end()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton: return
        for node,center in self.points.items():
            if hypot(center.x()-event.position().x(),center.y()-event.position().y())<27:
                self.choose(node)
                break

    def mouseMoveEvent(self,event):
        for node,center in self.points.items():
            if hypot(center.x()-event.position().x(),center.y()-event.position().y())<27:
                neighbors=', '.join(f'{n} ({w})' for n,w,_ in self.model.adjacency[node])
                cost=fmt(self.step.distances[node]) if self.step else '∞'
                self.setToolTip(f'Nodo {node} · g={cost}\nVecinos: {neighbors}')
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        self.setToolTip('')
        self.setCursor(Qt.CursorShape.ArrowCursor)
