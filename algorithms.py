"""Dijkstra, BFS, DFS, fuerza bruta y voraz manuales con instantáneas independientes para retroceder.

No se invoca ningún algoritmo de búsqueda o caminos de igraph. heapq solo
implementa la cola de prioridad y deque la cola FIFO.
"""
from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from math import inf, hypot
from graph_data import GraphModel

ALGORITHMS = ('Dijkstra', 'BFS · anchura', 'DFS · profundidad',
              'Fuerza bruta · exhaustiva', 'Voraz · arista mínima', 'A*', 'Bellman–Ford')

DESCRIPTIONS = {
    ALGORITHMS[5]: 'A*: prioriza f = g + h; h geométrica escalada y consistente.',
    ALGORITHMS[6]: 'Bellman–Ford: relaja los arcos y detecta ciclos negativos.',
    ALGORITHMS[0]: 'Menor costo acumulado pendiente; óptimo con pesos ≥ 0.',
    ALGORITHMS[1]: 'Menor número de aristas; no garantiza menor peso.',
    ALGORITHMS[2]: 'Explora en profundidad; no garantiza una ruta mínima.',
    ALGORITHMS[3]: 'Compara caminos simples; mínimo simple al completar todos.',
    ALGORITHMS[4]: 'Elige la arista local más barata; puede fallar o costar más.',
}

@dataclass(frozen=True)
class Step:
    message: str
    current: int | None
    visited: frozenset[int]
    frontier: frozenset[int]
    distances: dict[int, float]
    parents: dict[int, tuple[int, int]]
    active_edge: int | None = None
    path_nodes: tuple[int, ...] = ()
    path_edges: tuple[int, ...] = ()
    done: bool = False
    limited: bool = False
    candidates: int = 0
    branch_nodes: tuple[int, ...] = ()
    branch_edges: tuple[int, ...] = ()
    heuristic: dict[int, float] | None = None
    pass_number: int = 0
    negative_nodes: frozenset[int] = frozenset()


def search(model: GraphModel, source: int, target: int, algorithm: str = 'Dijkstra',
           max_steps: int | None = 10000) -> list[Step]:
    if source not in model.adjacency or target not in model.adjacency:
        raise ValueError('El origen y el destino deben existir en el grafo.')
    if algorithm not in ALGORITHMS:
        raise ValueError('Algoritmo desconocido.')
    if algorithm in ('Dijkstra', 'A*') and model.has_negative_weights:
        raise ValueError(f'{algorithm} requiere pesos no negativos. Usa Bellman–Ford.')
    if algorithm == ALGORITHMS[5]:
        return a_star(model, source, target)
    if algorithm == ALGORITHMS[6]:
        return bellman_ford(model, source, target)
    if algorithm == ALGORITHMS[3]:
        return list(brute_force(model, source, target, max_steps))
    if algorithm == ALGORITHMS[4]:
        return greedy(model, source, target)
    weighted = algorithm == 'Dijkstra'
    breadth = algorithm == ALGORITHMS[1]
    distances = {n: inf for n in model.nodes}
    distances[source] = 0
    parents = {}
    visited, frontier = set(), {source}
    steps = []

    def snapshot(message, current=None, edge=None, done=False, path=(), path_edges=()):
        steps.append(Step(message, current, frozenset(visited), frozenset(frontier),
                          distances.copy(), parents.copy(), edge, tuple(path), tuple(path_edges), done))

    priority = [(0, source)]
    queue = deque([source])
    stack = [source]
    discovered = {source}
    snapshot(f'Inicio en {source}. Destino: {target}. Distancia inicial: 0.')
    while priority if weighted else queue if breadth else stack:
        if weighted:
            cost, node = heappop(priority)
            if node in visited or cost != distances[node]:
                continue
        else:
            node = queue.popleft() if breadth else stack.pop()
        frontier.discard(node)
        visited.add(node)
        reason = (' Es el menor costo acumulado de toda la frontera; queda confirmado.'
                  if weighted else '')
        snapshot(f'Visitar {node}: costo acumulado {distances[node]:g}.' + reason, node)
        if node == target:
            path, edge_path = [target], []
            while path[-1] != source:
                parent, edge_id = parents[path[-1]]
                path.append(parent)
                edge_path.append(edge_id)
            path.reverse()
            edge_path.reverse()
            qualifier = 'mínimo' if weighted else 'de la ruta encontrada'
            snapshot(f'Destino alcanzado. Costo {qualifier}: {distances[target]:g}. '
                     + ' → '.join(map(str, path)), node, done=True, path=path, path_edges=edge_path)
            return steps
        # DFS inserta en orden inverso para visitar primero la etiqueta menor.
        neighbors = model.adjacency[node] if weighted or breadth else reversed(model.adjacency[node])
        for neighbor, weight, edge_id in neighbors:
            if neighbor in visited:
                continue
            candidate = distances[node] + weight
            improve = candidate < distances[neighbor] if weighted else neighbor not in discovered
            old = distances[neighbor]
            if improve:
                distances[neighbor] = candidate
                parents[neighbor] = (node, edge_id)
                frontier.add(neighbor)
                discovered.add(neighbor)
                if weighted:
                    heappush(priority, (candidate, neighbor))
                elif breadth:
                    queue.append(neighbor)
                else:
                    stack.append(neighbor)
            before = '∞' if old == inf else f'{old:g}'
            action = f'Actualizar costo: {before} → {candidate:g}.' if improve else 'Sin actualización.'
            snapshot(f'Examinar {node} → {neighbor}, peso {weight}: '
                     f'{distances[node]:g} + {weight} = {candidate:g}. {action}', node, edge_id)
    snapshot(f'No existe una ruta entre {source} y {target}.', done=True)
    return steps


def greedy(model: GraphModel, source: int, target: int) -> list[Step]:
    """Voraz local: el vecino no visitado con arista más barata, sin retroceso.

    No es greedy best-first con heurística: la imagen no proporciona una
    estimación admisible al destino. Dijkstra también es un algoritmo voraz,
    pero aplica su elección al costo acumulado de toda la frontera.
    """
    if source not in model.adjacency or target not in model.adjacency:
        raise ValueError('El origen y el destino deben existir en el grafo.')
    distances = {n: inf for n in model.nodes}
    distances[source] = 0
    node, visited, parents = source, {source}, {}
    path, edges, steps = [source], [], []

    def snapshot(message, edge=None, done=False, success=False):
        frontier = frozenset(n for n, _, _ in model.adjacency[node] if n not in visited)
        steps.append(Step(message, node, frozenset(visited), frontier, distances.copy(),
                          parents.copy(), edge, tuple(path) if success else (),
                          tuple(edges) if success else (), done,
                          branch_nodes=tuple(path), branch_edges=tuple(edges)))

    snapshot(f'Voraz local: comenzar en {source}. Elegir por peso de arista, no costo global.')
    while node != target:
        options = [(n, w, e) for n, w, e in model.adjacency[node] if n not in visited]
        if not options:
            snapshot(f'Voraz quedó bloqueado en {node}. No retrocede; '
                     'esto no demuestra que el destino sea inalcanzable.', done=True)
            return steps
        selected = min(options, key=lambda item: (item[1], item[0], item[2]))
        for neighbor, weight, edge_id in options:
            choice = 'Elegida: es el menor peso local.' if edge_id == selected[2] else 'Descartada por la regla local.'
            snapshot(f'Comparar {node} → {neighbor}, peso {weight}. {choice}', edge_id)
        neighbor, weight, edge_id = selected
        parents[neighbor] = (node, edge_id)
        distances[neighbor] = distances[node] + weight
        node = neighbor
        path.append(node)
        edges.append(edge_id)
        visited.add(node)
        snapshot(f'Avanzar a {node}: costo acumulado {distances[node]:g}.', edge_id)
    snapshot(f'Ruta voraz encontrada, costo {distances[target]:g} (sin garantía de mínimo): '
             + ' → '.join(map(str, path)), done=True, success=True)
    return steps


def brute_force(model: GraphModel, source: int, target: int, max_steps: int | None = None):
    """Generador exhaustivo de todos los caminos simples, distinguiendo aristas.

    No poda por costo ni se detiene en el primer camino encontrado. Evita repetir
    nodos dentro del camino para excluir ciclos: con pesos no negativos existe
    un camino mínimo simple. El límite opcional produce un resultado provisional
    explícito. El generador permite pausar la interfaz entre cada operación.
    """
    if source not in model.adjacency or target not in model.adjacency:
        raise ValueError('El origen y el destino deben existir en el grafo.')
    if max_steps is not None and max_steps < 1:
        raise ValueError('El límite debe ser positivo o None.')
    path, edge_path, route_costs = [source], [], [0]
    seen = {source}
    best_path, best_edges, best_cost = (), (), inf
    candidates = 0

    def snapshot(message, edge=None, done=False, limited=False):
        shown_path = best_path if done and best_path else tuple(path)
        shown_edges = best_edges if done and best_path else tuple(edge_path)
        distances = {n: inf for n in model.nodes}
        parents = {}
        distances[source] = 0
        cost = 0
        for a, b, edge_id in zip(shown_path, shown_path[1:], shown_edges):
            cost += model.graph.es[edge_id]['weight']
            distances[b] = cost
            parents[b] = (a, edge_id)
        current = shown_path[-1]
        frontier = frozenset(n for n, _, _ in model.adjacency[current] if n not in shown_path)
        return Step(message, current, frozenset(seen), frontier, distances, parents, edge,
                    best_path if done else (), best_edges if done else (), done, limited,
                    candidates, tuple(shown_path), tuple(shown_edges))

    def enumerate_paths():
        nonlocal candidates, best_path, best_edges, best_cost
        node = path[-1]
        seen.add(node)
        yield snapshot(f'Explorar camino: {" → ".join(map(str, path))}. Costo {route_costs[-1]:g}.')
        if node == target:
            candidates += 1
            better = route_costs[-1] < best_cost
            if better:
                best_cost, best_path, best_edges = route_costs[-1], tuple(path), tuple(edge_path)
            yield snapshot(f'Camino completo #{candidates}: costo {route_costs[-1]:g}. '
                           f'Mejor hasta ahora: {best_cost:g}. Seguir buscando; aún no es definitivo.')
            return
        for neighbor, weight, edge_id in model.adjacency[node]:
            if neighbor in path:
                yield snapshot(f'Examinar {node} → {neighbor}, peso {weight}: omitir ciclo en este camino.', edge_id)
                continue
            yield snapshot(f'Examinar {node} → {neighbor}, peso {weight}: probar otra continuación.', edge_id)
            path.append(neighbor)
            edge_path.append(edge_id)
            route_costs.append(route_costs[-1] + weight)
            yield from enumerate_paths()
            path.pop()
            edge_path.pop()
            route_costs.pop()
            yield snapshot(f'Retroceder a {node} para probar la siguiente arista.', edge_id)

    traversal = enumerate_paths()
    emitted, limited = 0, False
    while max_steps is None or emitted < max_steps:
        try:
            step = next(traversal)
        except StopIteration:
            break
        emitted += 1
        yield step
    else:
        limited = True
        traversal.close()
    # Un límite es un corte de demostración, nunca una prueba de optimalidad.
    if limited:
        result = (f'Mejor ruta provisional: costo {best_cost:g}.' if best_path
                  else 'Aún no se encontró una ruta; puede existir.')
        message = (f'Límite de {max_steps} pasos alcanzado. {candidates} caminos completos. '
                   f'{result} Exploración incompleta: NO se garantiza el mínimo.')
    elif best_path:
        message = (f'Exploración exhaustiva terminada: {candidates} caminos completos. '
                   f'Menor costo de camino simple {best_cost:g}: ' + ' → '.join(map(str, best_path)))
    else:
        message = f'Exploración exhaustiva terminada. No existe una ruta entre {source} y {target}.'
    yield snapshot(message, done=True, limited=limited)


def reconstruct(parents, source, target):
    path, edge_path, seen = [target], [], {target}
    while path[-1] != source:
        if path[-1] not in parents:
            return (), ()
        parent, edge_id = parents[path[-1]]
        if parent in seen:
            raise ValueError('No se puede reconstruir una ruta finita con un ciclo en sus padres.')
        path.append(parent)
        edge_path.append(edge_id)
        seen.add(parent)
    return tuple(reversed(path)), tuple(reversed(edge_path))


def consistent_heuristic(model, target):
    """h(v)=k*distancia(v,t), k=min(w(u,v)/longitud(u,v)).

    Por desigualdad triangular h(u) <= w(u,v)+h(v). Un peso cero puede
    hacer k=0: A* se reduce correctamente a Dijkstra. No usa rutas precalculadas.
    """
    if model.has_negative_weights:
        raise ValueError('A* requiere pesos no negativos.')
    positions = model.positions
    ratios = []
    for u in model.nodes:
        for v, weight, _ in model.adjacency[u]:
            length = hypot(positions[u][0]-positions[v][0], positions[u][1]-positions[v][1])
            if length > 0:
                ratios.append(weight / length)
    # Reducir mínimamente el factor evita sobreestimación por redondeo flotante.
    factor = min(ratios, default=0) * (1 - 1e-12)
    tx, ty = positions[target]
    return {n: factor * hypot(x-tx, y-ty) for n, (x, y) in positions.items()}


def a_star(model, source, target):
    h = consistent_heuristic(model, target)
    costs = {n: inf for n in model.nodes}
    costs[source] = 0
    parents, visited, frontier, steps = {}, set(), {source}, []
    queue = [(h[source], 0, source)]

    def snapshot(message, current=None, edge=None, done=False, path=(), path_edges=()):
        steps.append(Step(message, current, frozenset(visited), frozenset(frontier),
                          costs.copy(), parents.copy(), edge, path, path_edges, done,
                          heuristic=h.copy()))

    snapshot(f'A*: comenzar en {source}; f = g + h. h({target}) = 0.')
    while queue:
        f, g, node = heappop(queue)
        if node in visited or g != costs[node]:
            continue
        visited.add(node)
        frontier.discard(node)
        snapshot(f'Elegir {node}: g={g:g}, h={h[node]:.3f}, f={f:.3f}; menor f pendiente.', node)
        if node == target:
            path, edges = reconstruct(parents, source, target)
            snapshot(f'A*: destino confirmado. Costo mínimo {g:g}: '
                     + ' → '.join(map(str, path)), node, done=True, path=path, path_edges=edges)
            return steps
        for neighbor, weight, edge_id in model.adjacency[node]:
            candidate = g + weight
            old = costs[neighbor]
            improve = candidate < old
            if improve:
                costs[neighbor] = candidate
                parents[neighbor] = (node, edge_id)
                frontier.add(neighbor)
                visited.discard(neighbor)
                heappush(queue, (candidate + h[neighbor], candidate, neighbor))
            before = '∞' if old == inf else f'{old:g}'
            snapshot(f'Relajar {node} → {neighbor}: ¿{candidate:g} < {before}? '
                     + (f'Sí. g={candidate:g}, h={h[neighbor]:.3f}, f={candidate+h[neighbor]:.3f}.'
                        if improve else 'No. Mantener costo.'), node, edge_id)
    snapshot(f'A*: no existe ruta de {source} a {target}.', done=True)
    return steps


def bellman_ford(model, source, target):
    costs = {n: inf for n in model.nodes}
    costs[source] = 0
    parents, visited, steps = {}, set(), []
    arcs = [(u, v, w, e) for u in model.nodes for v, w, e in model.adjacency[u]]

    def snapshot(message, current=None, edge=None, iteration=0, done=False, path=(), edges=(), negative=frozenset()):
        frontier = frozenset(n for n in model.nodes if costs[n] != inf and n not in visited)
        steps.append(Step(message, current, frozenset(visited), frontier, costs.copy(),
                          parents.copy(), edge, path, edges, done, pass_number=iteration,
                          negative_nodes=negative))

    snapshot(f'Bellman–Ford: origen {source}. Se permiten pesos negativos.')
    for iteration in range(1, len(model.nodes)):
        changed = False
        visited.clear()
        snapshot(f'Pasada {iteration}/{len(model.nodes)-1}: recorrer todos los arcos.', iteration=iteration)
        for u, v, weight, edge_id in arcs:
            candidate = costs[u] + weight
            old = costs[v]
            improve = costs[u] != inf and candidate < old
            if improve:
                costs[v] = candidate
                parents[v] = (u, edge_id)
                changed = True
            if costs[u] != inf:
                visited.add(u)
            before = '∞' if old == inf else f'{old:g}'
            total = '∞' if candidate == inf else f'{candidate:g}'
            snapshot(f'Pasada {iteration}, relajar {u} → {v}, peso {weight}: '
                     f'¿{total} < {before}? ' + ('Sí, actualizar.' if improve else 'No, conservar.'),
                     u, edge_id, iteration)
        if not changed:
            snapshot('Ninguna mejora en esta pasada: las distancias finitas quedan estables.', iteration=iteration)
            break
    affected = set()
    for u, v, weight, edge_id in arcs:
        unstable = costs[u] != inf and costs[u] + weight < costs[v]
        snapshot(f'Comprobar ciclo negativo en {u} → {v}: '
                 + ('todavía mejora; marcar destinos afectados.' if unstable else 'sin mejora.'), u, edge_id)
        if unstable:
            affected.add(v)
    pending = list(affected)
    while pending:
        node = pending.pop()
        for neighbor, _, _ in model.adjacency[node]:
            if neighbor not in affected:
                affected.add(neighbor)
                pending.append(neighbor)
    for node in affected:
        costs[node] = -inf
        parents.pop(node, None)
    negative = frozenset(affected)
    if target in affected:
        snapshot('Ciclo negativo alcanzable que afecta al destino: costo −∞. '
                 'No existe un camino mínimo finito.', target, done=True, negative=negative)
    elif costs[target] == inf:
        snapshot(f'No existe ruta de {source} a {target}.', done=True, negative=negative)
    else:
        path, edges = reconstruct(parents, source, target)
        suffix = ' Hay un ciclo negativo en otra rama; no afecta a este destino.' if affected else ''
        snapshot(f'Bellman–Ford: costo mínimo {costs[target]:g}: '
                 + ' → '.join(map(str, path)) + suffix, target, done=True,
                 path=path, edges=edges, negative=negative)
    return steps
