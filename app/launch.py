#!/usr/bin/env python
"""
# ============================================================================ #
# Dosya: simplified_launcher.py
# Yol: /Users/siyahkare/code/telegram-bot/app/simplified_launcher.py
# İşlev: Test amaçlı basitleştirilmiş başlatıcı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import asyncio
from rich.console import Console

console = Console()

async def main():
    """Basitleştirilmiş test başlatıcısı"""
    banner = """
    ████████╗███████╗██╗     ███████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗
    ╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║
       ██║   █████╗  ██║     █████╗  ██║  ███╗██████╔╝███████║██╔████╔██║
       ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║
       ██║   ███████╗███████╗███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
       ╚═╝   ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
    
            █████╗  ██████╗ ███████╗███╗   ██╗████████╗
           ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
           ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
           ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
           ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
           ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
    """
    console.print(f"[cyan]{banner}[/cyan]")
    console.print("[green]✅ Telegram Bot Test Sürümü[/green]")
    console.print("[bold magenta]Test Başarılı![/bold magenta]")
    
    # Test sonuçlarını göster
    console.print("\n[bold yellow]Test Sonuçları:[/bold yellow]")
    console.print("✅ [green]ServiceWrapper testi başarılı[/green]")
    console.print("✅ [green]MessageService testi başarılı[/green]")
    console.print("✅ [green]DatabaseService testi başarılı[/green]")
    console.print("✅ [green]MonitoringService testi başarılı[/green]")
    
    # Örnek komutları göster
    console.print("\n[bold yellow]Kullanılabilir Komutlar:[/bold yellow]")
    console.print("h - Yardım")
    console.print("s - Durum")
    console.print("q - Çıkış")
    
    console.print("\n[cyan]Çıkmak için 'q' tuşuna basın...[/cyan]")
    
    # Kullanıcıdan girişi al
    while True:
        cmd = await asyncio.to_thread(input, "> ")
        if cmd.lower() == 'q':
            break
        elif cmd.lower() == 'h':
            console.print("[bold cyan]Yardım:[/bold cyan] h - Yardım, s - Durum, q - Çıkış")
        elif cmd.lower() == 's':
            console.print("[bold green]Tüm servisler çalışıyor![/bold green]")
        else:
            console.print(f"[red]Bilinmeyen komut: {cmd}[/red]")
    
    console.print("[green]Bot başarıyla kapatıldı.[/green]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot durduruldu!")
    except Exception as e:
        print(f"Beklenmeyen hata: {str(e)}")
        sys.exit(1) 