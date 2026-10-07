import json
import tempfile
import unittest
from math import inf
from pathlib import Path
from algorithms import search, consistent_heuristic
from graph_data import build_graph, load_graph

class NewAlgorithmsTests(unittest.TestCase):
    def test_a_star_all_900_pairs_and_heuristic_consistency(self):
        model=build_graph()
        for target in model.nodes:
            h=consistent_heuristic(model,target)
            self.assertEqual(h[target],0)
            for u in model.nodes:
                for v,w,_ in model.adjacency[u]:
                    self.assertLessEqual(h[u],w+h[v]+1e-9)
            for source in model.nodes:
                result=search(model,source,target,'A*')[-1]
                reference=search(model,source,target)[-1]
                self.assertEqual(result.distances[target],reference.distances[target],(source,target))
                self.assertTrue(result.done)
                self.assertEqual(result.path_nodes[0],source)
                self.assertEqual(result.path_nodes[-1],target)
                self.assertEqual(sum(model.graph.es[e]['weight'] for e in result.path_edges),result.distances[target])

    def test_bellman_ford_original_all_900_pairs(self):
        model=build_graph()
        for source in model.nodes:
            for target in model.nodes:
                result=search(model,source,target,'Bellman–Ford')[-1]
                self.assertEqual(result.distances[target],search(model,source,target)[-1].distances[target])
                self.assertFalse(result.negative_nodes)
                self.assertEqual(sum(model.graph.es[e]['weight'] for e in result.path_edges),result.distances[target])

    def test_directed_negative_edges_without_cycle(self):
        model=build_graph([(0,1,4),(0,2,5),(1,2,-3)],{0:(0,0),1:(100,0),2:(100,100)},True)
        result=search(model,0,2,'Bellman–Ford')[-1]
        self.assertEqual(result.distances[2],1)
        self.assertEqual(result.path_nodes,(0,1,2))
        self.assertNotIn((0,4,0),model.adjacency[1])
        for algorithm in ('Dijkstra','A*'):
            with self.assertRaises(ValueError): search(model,0,2,algorithm)

    def test_negative_cycle_affecting_target_and_undirected_negative_edge(self):
        for directed,edges in ((True,[(0,1,1),(1,2,-2),(2,1,1),(2,3,2)]),
                               (False,[(0,1,-1),(1,2,1),(2,3,1)])):
            model=build_graph(edges,{n:(n*80,0) for n in range(4)},directed)
            result=search(model,0,3,'Bellman–Ford')[-1]
            self.assertEqual(result.distances[3],-inf)
            self.assertIn(3,result.negative_nodes)
            self.assertEqual(result.path_nodes,())
            self.assertIn('No existe un camino mínimo finito',result.message)

    def test_negative_cycle_in_unreachable_or_separate_branch(self):
        positions={n:(n*80,0) for n in range(5)}
        for edges in ([(0,4,8),(1,2,-2),(2,1,1)],[(0,4,8),(0,1,1),(1,2,-2),(2,1,1)]):
            model=build_graph(edges,positions,True)
            result=search(model,0,4,'Bellman–Ford')[-1]
            self.assertEqual(result.distances[4],8)
            self.assertEqual(result.path_nodes,(0,4))
            self.assertNotIn(4,result.negative_nodes)

    def test_zero_edges_identity_disconnected_and_snapshot_isolation(self):
        model=build_graph([(0,1,0)],{0:(0,0),1:(100,0),2:(200,0)},True)
        self.assertEqual(consistent_heuristic(model,1),{0:0,1:0,2:0})
        for algorithm in ('A*','Bellman–Ford'):
            steps=search(model,0,1,algorithm)
            self.assertEqual(steps[-1].distances[1],0)
            self.assertEqual(steps[0].distances[1],inf)
            self.assertIsNot(steps[0].distances,steps[-1].distances)
            self.assertEqual(search(model,0,0,algorithm)[-1].path_nodes,(0,))
            self.assertEqual(search(model,0,2,algorithm)[-1].path_nodes,())
            with self.assertRaises(ValueError): search(model,8,1,algorithm)
        loop=build_graph([(0,0,-1)],{0:(0,0)},True)
        self.assertEqual(search(loop,0,0,'Bellman–Ford')[-1].distances[0],-inf)

    def test_json_validation_and_directed_loading(self):
        data={'directed':True,'nodes':[{'id':0,'x':0,'y':0},{'id':1,'x':200,'y':30}],'edges':[[0,1,-2]]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'negative.json'
            path.write_text(json.dumps(data))
            model=load_graph(path)
            self.assertTrue(model.has_negative_weights)
            self.assertTrue(model.graph.is_directed())
            self.assertEqual(model.adjacency[1],[])
            self.assertEqual(model.positions[1],(200,30))
            data['nodes'].append(data['nodes'][0])
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError): load_graph(path)
        with self.assertRaises(ValueError): build_graph([(0,2,1)],{0:(0,0)},True)
        with self.assertRaises(ValueError): build_graph([(0,1,float('nan'))],{0:(0,0),1:(1,1)},True)

if __name__=='__main__': unittest.main()
