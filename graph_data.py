"""Transcripción del multigrafo no dirigido de la imagen adjunta.

Las coordenadas conservan la distribución original. Los índices internos de
igraph no son las etiquetas numéricas de los nodos.
"""
from dataclasses import dataclass
import igraph as ig

POSITIONS = {
    29: (53, 52), 7: (248, 52), 21: (53, 198), 24: (53, 428),
    11: (194, 311), 14: (317, 316), 6: (473, 199), 9: (473, 316),
    10: (321, 492), 27: (297, 648), 4: (482, 624), 18: (575, 624),
    66: (673, 760), 13: (834, 756), 16: (927, 643), 12: (722, 512),
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
    (27, 4, 3), (27, 66, 1), (4, 8, 15), (4, 18, 5),
    (18, 12, 4), (18, 66, 6), (8, 15, 2), (8, 1, 7), (8, 12, 9),
    (15, 0, 8), (15, 1, 8), (0, 44, 70), (0, 1, 2),
    (44, 3, 80), (44, 5, 69), (3, 5, 2), (3, 2, 9), (3, 69, 6),
    (1, 2, 3), (1, 23, 7), (1, 12, 7), (23, 2, 3), (23, 16, 11),
    (2, 69, 11), (2, 17, 5), (5, 69, 3), (5, 20, 2),
    (69, 20, 3), (69, 25, 6), (69, 17, 4), (69, 70, 8),
    (20, 25, 7), (25, 70, 17), (17, 70, 6), (17, 16, 7),
    (12, 16, 16), (12, 16, 3), (12, 66, 7), (12, 13, 9),
    (16, 13, 3), (66, 13, 777),
]

@dataclass
class GraphModel:
    graph: ig.Graph
    nodes: tuple[int, ...]
    adjacency: dict[int, list[tuple[int, int, int]]]


def build_graph() -> GraphModel:
    nodes = tuple(sorted(POSITIONS))
    index = {node: i for i, node in enumerate(nodes)}
    graph = ig.Graph(n=len(nodes), edges=[(index[a], index[b]) for a, b, _ in EDGES], directed=False)
    graph.vs['name'] = [str(n) for n in nodes]
    graph.vs['label'] = list(nodes)
    graph.vs['position'] = [POSITIONS[n] for n in nodes]
    graph.es['weight'] = [w for _, _, w in EDGES]
    adjacency = {node: [] for node in nodes}
    # igraph almacena el multigrafo; los algoritmos recorren esta lista en Python.
    for edge in graph.es:
        a, b = (nodes[i] for i in edge.tuple)
        weight = edge['weight']
        if weight < 0:
            raise ValueError('Dijkstra requiere pesos no negativos.')
        adjacency[a].append((b, weight, edge.index))
        adjacency[b].append((a, weight, edge.index))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1], item[2]))
    return GraphModel(graph, nodes, adjacency)
