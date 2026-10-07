"""Exportación incremental; cancelar conserva las imágenes ya escritas y su manifiesto."""
import json
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from rendering import render_slide

class ExportJob(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self,folder,steps,model,source,target,algorithm,graph_name,total,parent=None):
        super().__init__(parent)
        self.folder=Path(folder)
        self.iterator=iter(steps)
        self.model=model
        self.source,self.target=source,target
        self.algorithm,self.graph_name=algorithm,graph_name
        self.total,self.count=total,0
        self.last=None
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.ended=False

    def start(self):
        if self.ended: return
        try:
            self.folder.mkdir(parents=True,exist_ok=False)
            self.manifest('exportando')
            self.timer.start(1)
        except (OSError,ValueError) as error:
            self.ended=True
            self.failed.emit(str(error))

    def manifest(self,status):
        data={'status':status,'algorithm':self.algorithm,'graph':self.graph_name,
              'source':self.source,'target':self.target,'images':self.count,
              'search_complete':bool(self.last and self.last.done and not self.last.limited),
              'limited':bool(self.last and self.last.limited),
              'negative_nodes':sorted(self.last.negative_nodes) if self.last else [],
              'last_message':self.last.message if self.last else '',
              'directed':self.model.graph.is_directed(),
              'edges':[[self.model.nodes[e.source],self.model.nodes[e.target],e['weight']]
                       for e in self.model.graph.es]}
        path=self.folder/'proceso.json'
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

    def tick(self):
        try:
            step=next(self.iterator)
        except StopIteration:
            self.finish('completo')
            return
        try:
            image=render_slide(self.model,step,self.source,self.target,self.algorithm,self.graph_name,
                               self.count,self.total)
            path=self.folder/f'paso-{self.count+1:06d}.png'
            if not image.save(str(path),'PNG'):
                raise OSError(f'No se pudo guardar {path}')
            self.last=step
            self.count+=1
            self.progress.emit(self.count)
            if step.done:
                self.finish('completo')
        except (OSError,ValueError,RuntimeError) as error:
            self.timer.stop()
            self.ended=True
            try: self.manifest('error')
            except OSError: pass
            self.failed.emit(str(error))

    def finish(self,status):
        if self.ended: return
        self.timer.stop()
        self.ended=True
        if hasattr(self.iterator,'close'): self.iterator.close()
        try:
            if self.folder.exists(): self.manifest(status)
        except OSError as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(str(self.folder))

    def cancel(self):
        self.finish('cancelado')
