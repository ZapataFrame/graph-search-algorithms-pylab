"""Pruebas con unittest, sin funciones de rutas de bibliotecas externas."""
import unittest
from collections import deque
from math import inf
import igraph as ig
from algorithms import search, brute_force, ALGORITHMS
from graph_data import build_graph, GraphModel, EDGES

class AlgorithmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = build_graph()
        nodes = cls.model.nodes
        # Oráculo independiente: recurrencia de Floyd–Warshall escrita en Python.
        cls.costs = {(a, b): 0 if a == b else inf for a in nodes for b in nodes}
        for a, b, weight in EDGES:
            cls.costs[a, b] = cls.costs[b, a] = min(cls.costs[a, b], weight)
        for k in nodes:
            for a in nodes:
                for b in nodes:
                    cls.costs[a, b] = min(cls.costs[a, b], cls.costs[a, k] + cls.costs[k, b])

    def assert_route(self, source, target, result):
        self.assertTrue(result.done)
        self.assertEqual(result.path_nodes[0], source)
        self.assertEqual(result.path_nodes[-1], target)
        total = 0
        for a, b, edge_id in zip(result.path_nodes, result.path_nodes[1:], result.path_edges):
            edge = self.model.graph.es[edge_id]
            endpoints = {self.model.nodes[i] for i in edge.tuple}
            self.assertEqual(endpoints, {a, b})
            total += edge['weight']
        self.assertEqual(total, result.distances[target])

    def test_transcription_and_parallel_edges(self):
        self.assertEqual(self.model.graph.vcount(), 30)
        self.assertEqual(self.model.graph.ecount(), 63)
        self.assertEqual(sorted(w for a, b, w in EDGES if {a, b} == {12, 16}), [3, 16])
        self.assertIn((66, 13, 777), EDGES)

    def test_dijkstra_all_900_pairs(self):
        for source in self.model.nodes:
            for target in self.model.nodes:
                result = search(self.model, source, target)[-1]
                self.assertEqual(result.distances[target], self.costs[source, target], (source, target))
                self.assert_route(source, target, result)

    def test_bfs_minimizes_hops_and_dfs_returns_valid_routes(self):
        for source in self.model.nodes:
            hops, queue = {source: 0}, deque([source])
            while queue:
                node = queue.popleft()
                for neighbor, _, _ in self.model.adjacency[node]:
                    if neighbor not in hops:
                        hops[neighbor] = hops[node] + 1
                        queue.append(neighbor)
            for target in self.model.nodes:
                bfs = search(self.model, source, target, ALGORITHMS[1])[-1]
                self.assertEqual(len(bfs.path_edges), hops[target])
                self.assert_route(source, target, bfs)
                self.assert_route(source, target, search(self.model, source, target, ALGORITHMS[2])[-1])

    def test_dijkstra_does_not_stop_on_first_discovery(self):
        steps = search(self.model, 66, 13)
        first_discovery = next(s for s in steps if s.distances[13] != inf)
        self.assertEqual(first_discovery.distances[13], 777)
        self.assertFalse(first_discovery.done)
        self.assertEqual(steps[-1].distances[13], 13)
        self.assertEqual(steps[-1].path_nodes, (66, 12, 16, 13))

    def test_identity_and_snapshot_isolation(self):
        steps = search(self.model, 29, 29)
        self.assertEqual(steps[-1].path_nodes, (29,))
        self.assertEqual(steps[-1].distances[29], 0)
        steps = search(self.model, 29, 13)
        self.assertEqual(steps[0].visited, frozenset())
        self.assertEqual(steps[0].distances[13], inf)
        self.assertIsNot(steps[0].distances, steps[-1].distances)
        self.assertEqual(steps[0].parents, {})

    def test_disconnected_and_invalid_nodes(self):
        model = GraphModel(ig.Graph(n=2), (1, 2), {1: [], 2: []})
        result = search(model, 1, 2)[-1]
        self.assertTrue(result.done)
        self.assertEqual(result.path_nodes, ())
        self.assertEqual(result.distances[2], inf)
        with self.assertRaises(ValueError): search(model, 0, 2)
        with self.assertRaises(ValueError): search(model, 1, 2, 'inválido')

class AdditionalAlgorithmTests(unittest.TestCase):
    @staticmethod
    def model(edges, nodes):
        graph = ig.Graph(n=len(nodes), edges=[(nodes.index(a), nodes.index(b)) for a, b, _ in edges])
        graph.es['weight'] = [w for _, _, w in edges]
        adjacency = {n: [] for n in nodes}
        for i, (a, b, w) in enumerate(edges):
            adjacency[a].append((b, w, i))
            adjacency[b].append((a, w, i))
        for options in adjacency.values(): options.sort()
        return GraphModel(graph, tuple(nodes), adjacency)

    def test_exhaustive_does_not_stop_at_first_path(self):
        model = self.model([(0, 1, 1), (1, 3, 100), (0, 2, 2), (2, 3, 1)], [0, 1, 2, 3])
        steps = list(brute_force(model, 0, 3))
        candidates = [s for s in steps if s.message.startswith('Camino completo #')]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].distances[3], 101)
        self.assertEqual(candidates[1].distances[3], 3)
        result = steps[-1]
        self.assertTrue(result.done)
        self.assertFalse(result.limited)
        self.assertEqual(result.path_nodes, (0, 2, 3))
        self.assertEqual(result.distances[3], 3)
        self.assertEqual(result.candidates, 2)
        self.assertEqual(steps[0].parents, {})

    def test_exhaustive_parallel_edges_and_all_small_graph_pairs(self):
        model = self.model([(0, 1, 9), (0, 1, 2), (1, 2, 3), (0, 2, 8), (2, 3, 1)], [0, 1, 2, 3])
        for a in model.nodes:
            for b in model.nodes:
                brute = search(model, a, b, ALGORITHMS[3], max_steps=None)[-1]
                self.assertFalse(brute.limited)
                self.assertEqual(brute.distances[b], search(model, a, b)[-1].distances[b])
        result = list(brute_force(model, 0, 2))[-1]
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.path_edges, (1, 2))

    def test_cutoff_is_explicit_and_no_hidden_candidates(self):
        model = self.model([(0, 1, 1), (1, 3, 100), (0, 2, 2), (2, 3, 1)], [0, 1, 2, 3])
        full = list(brute_force(model, 0, 3))
        for limit in range(1, len(full) - 1):
            limited = list(brute_force(model, 0, 3, limit))
            self.assertEqual(len(limited), limit + 1)
            self.assertTrue(limited[-1].limited)
            self.assertIn('NO se garantiza', limited[-1].message)
            self.assertEqual(limited[-1].candidates, limited[-2].candidates)
        with self.assertRaises(ValueError): list(brute_force(model, 0, 3, 0))

    def test_greedy_can_be_suboptimal_or_stuck(self):
        model = self.model([(0, 1, 1), (1, 3, 100), (0, 2, 2), (2, 3, 1)], [0, 1, 2, 3])
        greedy = search(model, 0, 3, ALGORITHMS[4])[-1]
        self.assertEqual(greedy.distances[3], 101)
        self.assertEqual(search(model, 0, 3)[-1].distances[3], 3)
        model = self.model([(0, 1, 1), (0, 2, 2), (2, 3, 1)], [0, 1, 2, 3])
        result = search(model, 0, 3, ALGORITHMS[4])[-1]
        self.assertTrue(result.done)
        self.assertEqual(result.path_nodes, ())
        self.assertIn('no demuestra', result.message)
        self.assertEqual(search(model, 0, 3)[-1].distances[3], 3)

    def test_identity_disconnected_and_invalid_for_new_algorithms(self):
        model = self.model([], [0, 1])
        for algorithm in ALGORITHMS[3:]:
            self.assertEqual(search(model, 0, 0, algorithm)[-1].path_nodes, (0,))
            self.assertEqual(search(model, 0, 1, algorithm)[-1].path_nodes, ())
            with self.assertRaises(ValueError): search(model, 9, 0, algorithm)

if __name__ == '__main__':
    unittest.main(verbosity=2)
