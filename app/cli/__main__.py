"""
CLI komutları için ana giriş noktası
"""
import sys
import logging
import argparse

from app.cli import run_status, run_stop, run_templates, run_repair, run_fix_schema
from app.cli.start import run_start
from app.cli.status import run_status
from app.cli.stop import run_stop
from app.cli.dashboard import run_dashboard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

def main():
    """Ana CLI fonksiyonu"""
    parser = argparse.ArgumentParser(description="Telegram Bot CLI")
    
    subparsers = parser.add_subparsers(dest="command", help="Komut")
    
    # Status komutu
    status_parser = subparsers.add_parser("status", help="Bot durumunu göster")
    
    # Stop komutu
    stop_parser = subparsers.add_parser("stop", help="Botu durdur")
    
    # Templates komutu
    templates_parser = subparsers.add_parser("templates", help="Şablonları güncelle")
    
    # Repair komutu
    repair_parser = subparsers.add_parser("repair", help="Veritabanı onarımı")
    
    # Fix schema komutu
    fix_schema_parser = subparsers.add_parser("fix_schema", help="Veritabanı şemasını düzelt")
    
    # Start komutu
    start_parser = subparsers.add_parser("start", help="Tüm servisleri başlat")
    
    # Dashboard komutu
    dashboard_parser = subparsers.add_parser("dashboard", help="Web dashboard'u başlat")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Dashboard portu (varsayılan: 8000)")
    
    args = parser.parse_args()
    
    if args.command == "status":
        run_status()
    elif args.command == "stop":
        run_stop()
    elif args.command == "templates":
        run_templates()
    elif args.command == "repair":
        run_repair()
    elif args.command == "fix_schema":
        run_fix_schema()
    elif args.command == "start":
        run_start()
    elif args.command == "dashboard":
        port = getattr(args, "port", 8000)
        run_dashboard(port=port)
    else:
        parser.print_help()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 