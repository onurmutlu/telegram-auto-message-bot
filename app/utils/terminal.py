from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
import os
import platform

# Singleton konsol nesnesi
console = Console()

def clear_screen():
    """
    Terminal ekranını temizler, platformdan bağımsız çalışır.
    """
    # Windows için
    if platform.system() == "Windows":
        os.system("cls")
    # Linux, macOS ve diğer Unix benzeri sistemler için
    else:
        os.system("clear")
    
    return True

def print_banner(title, style="bold blue on white"):
    """
    Başlık için dekoratif banner yazdırır
    """
    width = len(title) + 10
    console.print("╔" + "═" * width + "╗", style=style)
    console.print("║" + " " * ((width - len(title)) // 2) + title + " " * ((width - len(title) + 1) // 2) + "║", style=style)
    console.print("╚" + "═" * width + "╝", style=style)
    console.print("")

def print_table(headers, rows, title=None):
    """
    Verilen başlıklar ve satırlarla tablo oluşturur
    """
    table = console.Table(title=title, show_header=True, header_style="bold magenta")
    
    # Sütunları ekle
    for header in headers:
        table.add_column(header)
        
    # Satırları ekle
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
        
    console.print(table)

def create_progress(description="İşleniyor", total=100):
    """
    Basit ilerleme çubuğu oluşturur
    """
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn()
    )
    task_id = progress.add_task(f"[cyan]{description}", total=total)
    return progress, task_id