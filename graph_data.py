"""Transcripción del multigrafo no dirigido de la imagen adjunta.

Las coordenadas conservan la distribución original. Los índices internos de
igraph no son las etiquetas numéricas de los nodos.
"""
from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
import igraph as ig

POSITIONS = {
    29: (53, 52), 7: (248, 52), 21: (53, 198), 24: (53, 428),
    11: (194, 311), 14: (317, 316), 6: (473, 199), 9: (473, 316),
    10: (321, 492), 27: (297, 648), 4: (482, 624), 18: (575, 624),
    666: (673, 760), 13: (834, 756), 16: (927, 643), 12: (722, 512),
    8: (599, 350), 15: (697, 199), 0: (873, 97), 44: (1014, 47),
    1: (873, 350), 23: (922, 463), 3: (1014, 199), 2: (1014, 350),
    5: (1181, 160), 69: (1181, 350), 20: (1332, 243),
    25: (1332, 428), 17: (1054, 531), 70: (1263, 585),
}
# (nodo A, nodo B, peso). Se mantienen las dos aristas 12–16.
EDGES = [
    (29, 7, 5), (29, 21, 3), (21, 24, 2), (21, 11, 2),
    (24, 11, 7), (7, 11, 5), (7, 14, 3), (7, 6, 10), (7, 1, 20),
    (11, 14, 9), (11, 10, 7), (14, 6, 5), (14, 9, 5),
    (14, 10, 9), (14, 4, 8), (6, 9, 7), (6, 8, 4), (6, 15, 3),
    (9, 10, 3), (10, 1, 5), (10, 4, 6), (10, 27, 9),
    (27, 4, 3), (27, 666, 1), (4, 8, 15), (4, 18, 5),
    (18, 12, 4), (18, 666, 6), (8, 15, 2), (8, 1, 7), (8, 12, 9),
    (15, 0, 8), (15, 1, 8), (0, 44, 70), (0, 1, 2),
    (44, 3, 80), (44, 5, 69), (3, 5, 2), (3, 2, 9), (3, 69, 6),
    (1, 2, 3), (1, 23, 7), (1, 12, 7), (23, 2, 3), (23, 16, 11),
    (2, 69, 11), (2, 17, 5), (5, 69, 3), (5, 20, 2),
    (69, 20, 3), (69, 25, 6), (69, 17, 4), (69, 70, 8),
    (20, 25, 7), (25, 70, 17), (17, 70, 6), (17, 16, 7),
    (12, 16, 16), (12, 16, 3), (12, 666, 7), (12, 13, 9),
    (16, 13, 3), (666, 13, 777),
]

@dataclass
class GraphModel:
    graph: ig.Graph
    nodes: tuple[int, ...]
    adjacency: dict[int, list[tuple[int, int, int]]]


    @property
    def positions(self):
        if 'position' in self.graph.vs.attributes():
            return {n: tuple(self.graph.vs[i]['position']) for i, n in enumerate(self.nodes)}
        return {n: POSITIONS.get(n, (80 + (i % 6) * 200, 80 + (i // 6) * 140))
                for i, n in enumerate(self.nodes)}

    @property
    def has_negative_weights(self):
        return any(edge['weight'] < 0 for edge in self.graph.es)


def build_graph(edges=None, positions=None, directed=False) -> GraphModel:
    positions = POSITIONS if positions is None else positions
    edges = EDGES if edges is None else edges
    if not positions:
        raise ValueError('El grafo debe contener nodos.')
    if not all(type(n) is int for n in positions):
        raise ValueError('Las etiquetas de los nodos deben ser enteros.')
    for position in positions.values():
        if len(position) != 2 or not all(type(x) in (int, float) and isfinite(x) for x in position):
            raise ValueError('Cada posición debe tener dos coordenadas finitas.')
    nodes = tuple(sorted(positions))
    index = {node: i for i, node in enumerate(nodes)}
    for edge in edges:
        if len(edge) != 3:
            raise ValueError('Cada arista debe indicar origen, destino y peso.')
        a, b, weight = edge
        if a not in index or b not in index:
            raise ValueError('Una arista hace referencia a un nodo inexistente.')
        if type(weight) not in (int, float) or not isfinite(weight):
            raise ValueError('Los pesos deben ser números finitos.')
    graph = ig.Graph(n=len(nodes), edges=[(index[a], index[b]) for a, b, _ in edges], directed=directed)
    graph.vs['name'] = [str(n) for n in nodes]
    graph.vs['label'] = list(nodes)
    graph.vs['position'] = [positions[n] for n in nodes]
    graph.es['weight'] = [w for _, _, w in edges]
    adjacency = {node: [] for node in nodes}
    for edge in graph.es:
        a, b = (nodes[i] for i in edge.tuple)
        adjacency[a].append((b, edge['weight'], edge.index))
        if not directed and a != b:
            adjacency[b].append((a, edge['weight'], edge.index))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1], item[2]))
    return GraphModel(graph, nodes, adjacency)


def load_graph(path: str | Path) -> GraphModel:
    """JSON: directed (bool), nodes [{id, x, y}], edges [[a, b, peso]]."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or type(data.get('directed')) is not bool:
        raise ValueError('El JSON debe especificar directed: true o false.')
    try:
        node_list = data['nodes']
        positions = {node['id']: (node['x'], node['y']) for node in node_list}
        if len(positions) != len(node_list):
            raise ValueError('Hay nodos duplicados.')
        return build_graph(data['edges'], positions, data['directed'])
    except (KeyError, TypeError) as error:
        raise ValueError('Formato inválido: se requieren nodes y edges.') from error
