"""Pruebas reales de Qt y PNG, en modo offscreen y carpetas temporales."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QPA_PLATFORMTHEME']=''
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage,QFont
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from main import Window,STYLE
from rendering import load_font,FONT,render_slide
from exporting import ExportJob
from graph_data import build_graph
from algorithms import ALGORITHMS,search,brute_force

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')
        cls.font=load_font()
        cls.app.setFont(QFont(FONT,11))
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.window=Window()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.pause()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_all_seven_algorithms_navigation_and_presentation(self):
        w=self.window
        self.assertEqual(self.font,'Excalifont')
        self.assertFalse(w.graph_choice.model().item(1).isEnabled())
        for name in ALGORITHMS:
            w.algorithm.setCurrentText(name)
            QTest.mouseClick(w.next,Qt.MouseButton.LeftButton)
            self.assertEqual(w.index,1)
            QTest.mouseClick(w.back,Qt.MouseButton.LeftButton)
            self.assertEqual(w.index,0)
        w.algorithm.setCurrentText('A*')
        w.navigate(3)
        self.assertNotEqual(w.table.item(0,2).text(),'—')
        QTest.mouseClick(w.presentation_button,Qt.MouseButton.LeftButton)
        self.assertEqual(w.sidebar_stack.currentIndex(),1)
        self.assertEqual(w.presentation_step.text(),w.steps[w.index].message)
        self.assertIn('Frontera',w.presentation_legend.text())
        QTest.mouseClick(w.presentation_button,Qt.MouseButton.LeftButton)
        self.assertEqual(w.sidebar_stack.currentIndex(),0)

    def test_import_negative_graph_and_restore_original(self):
        w=self.window
        data={'directed':True,'nodes':[{'id':0,'x':0,'y':0},{'id':1,'x':100,'y':80},{'id':2,'x':200,'y':0}],
              'edges':[[0,1,4],[1,2,-3],[0,2,5]]}
        path=self.root/'negative.json'
        path.write_text(json.dumps(data))
        with patch('main.QFileDialog.getOpenFileName',return_value=(str(path),'')):
            QTest.mouseClick(w.import_button,Qt.MouseButton.LeftButton)
        self.assertEqual(w.algorithm.currentText(),'Bellman–Ford')
        self.assertFalse(w.algorithm.model().item(ALGORITHMS.index('A*')).isEnabled())
        self.assertFalse(w.algorithm.model().item(0).isEnabled())
        w.source.setCurrentText('0')
        w.target.setCurrentText('2')
        w.navigate(len(w.steps)-1)
        self.assertEqual(w.canvas.step.distances[2],1)
        self.assertTrue(w.model.graph.is_directed())
        w.graph_choice.setCurrentIndex(0)
        self.assertIs(w.model,w.original_model)
        self.assertTrue(w.algorithm.model().item(0).isEnabled())

    def test_export_current_png_with_and_without_presentation(self):
        w=self.window
        w.algorithm.setCurrentText('A*')
        w.navigate(len(w.steps)-1)
        for presentation in (False,True):
            if presentation: w.toggle_presentation()
            path=self.root/f'export-{presentation}.png'
            with patch('main.QFileDialog.getSaveFileName',return_value=(str(path),'')):
                QTest.mouseClick(w.image_button,Qt.MouseButton.LeftButton)
            image=QImage(str(path))
            self.assertEqual((image.width(),image.height()),(1800,1120))
            self.assertEqual(image.pixelColor(0,0).name(),'#ffffff')
            # La vista y la exportación conservan el mismo paso.
            self.assertTrue(w.steps[w.index].done)
        self.assertNotEqual((self.root/'export-False.png').read_bytes(),(self.root/'export-True.png').read_bytes())

    def test_save_full_process_button_and_manifest(self):
        w=self.window
        w.source.setCurrentText('29')
        w.target.setCurrentText('29')
        with patch('main.QFileDialog.getExistingDirectory',return_value=str(self.root)):
            QTest.mouseClick(w.process_button,Qt.MouseButton.LeftButton)
        deadline=time.monotonic()+10
        while w.export_job is not None and time.monotonic()<deadline: QTest.qWait(10)
        self.assertIsNone(w.export_job)
        folder=next(self.root.glob('pylab-*'))
        data=json.loads((folder/'proceso.json').read_text())
        self.assertEqual(data['status'],'completo')
        self.assertTrue(data['search_complete'])
        self.assertEqual(data['images'],len(w.steps))
        self.assertEqual(len(list(folder.glob('paso-*.png'))),len(w.steps))
        self.assertEqual(len(data['edges']),63)

    def test_export_cancellation_and_brute_force_limit(self):
        model=build_graph([(0,1,1),(1,2,1)],{0:(0,0),1:(100,40),2:(200,0)},True)
        steps=search(model,0,2,'Bellman–Ford')
        job=ExportJob(self.root/'cancel',steps,model,0,2,'Bellman–Ford','Test',len(steps))
        job.start()
        job.timer.stop()
        job.tick()
        job.cancel()
        data=json.loads((job.folder/'proceso.json').read_text())
        self.assertEqual(data['status'],'cancelado')
        self.assertEqual(data['images'],1)
        self.assertFalse(data['search_complete'])
        job=ExportJob(self.root/'limited',brute_force(model,0,2,2),model,0,2,ALGORITHMS[3],'Test',3)
        job.start()
        job.timer.stop()
        for _ in range(3): job.tick()
        data=json.loads((job.folder/'proceso.json').read_text())
        self.assertTrue(data['limited'])
        self.assertFalse(data['search_complete'])
        self.assertEqual(data['images'],3)

if __name__=='__main__': unittest.main()
