import time
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console

class ProgressManager:
    def __init__(self):
        self.console = Console()
        self.active_progress = None
        
    def create_progress_bar(self, total=100, description="İşleniyor"):
        """
        Rich kütüphanesi kullanarak gelişmiş bir ilerleme çubuğu oluşturur.
        
        Args:
            total: Toplam iş miktarı
            description: İşlem açıklaması
            
        Returns:
            tuple: (progress, task_id) - ilerleme nesnesi ve görev kimliği
        """
        if self.active_progress:
            self.active_progress.stop()
            
        self.active_progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn()
        )
        
        task_id = self.active_progress.add_task(f"[cyan]{description}", total=total)
        self.active_progress.start()
        return self.active_progress, task_id
        
    def create_multi_progress(self, tasks):
        """
        Birden çok görevi izleyen ilerleme çubuğu oluşturur.
        
        Args:
            tasks: (açıklama, toplam) biçiminde görev listesi
            
        Returns:
            dict: görev açıklaması -> (progress, task_id) eşlemesi
        """
        if self.active_progress:
            self.active_progress.stop()
            
        self.active_progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeRemainingColumn()
        )
        
        task_map = {}
        for desc, total in tasks:
            task_id = self.active_progress.add_task(f"[cyan]{desc}", total=total)
            task_map[desc] = (self.active_progress, task_id)
            
        self.active_progress.start()
        return task_map
    
    def update_progress(self, progress, task_id, advance=1, message=None):
        """
        İlerleme çubuğunu günceller.
        
        Args:
            progress: İlerleme nesnesi
            task_id: Görev kimliği
            advance: Artış miktarı
            message: Opsiyonel durum mesajı
        """
        if message:
            progress.update(task_id, description=f"[cyan]{message}", advance=advance)
        else:
            progress.update(task_id, advance=advance)
            
    def complete_progress(self, progress, task_id, message="Tamamlandı!"):
        """
        İlerlemeyi tamamlar ve başarı mesajı gösterir.
        """
        progress.update(task_id, completed=100, description=f"[green]{message}")
        
    def stop(self):
        """
        Tüm aktif ilerleme çubuklarını durdurur.
        """
        if self.active_progress:
            self.active_progress.stop()
            self.active_progress = None

    def show_indeterminate(self, message="İşlem devam ediyor..."):
        """
        Belirsiz süreli işlemler için dönen gösterge.
        """
        from rich.live import Live
        from rich.spinner import Spinner
        
        spinner = Spinner("dots", text=message)
        with Live(spinner, refresh_per_second=10) as live:
            # Bu fonksiyonu çağıran kod, spinner'ı durdurmaktan sorumludur
            return live