"""
CLI'dan web dashboard başlatıcı
"""
import subprocess
import sys
import os
import argparse

def run_dashboard(port=None):
    """
    FastAPI tabanlı dashboard'u başlatır
    
    Args:
        port: Kullanılacak port numarası (varsayılan: 8000)
    """
    # Port numarasını belirleme
    if port is None:
        # CLI içinden çağrılması durumunda, sys.argv'dan port argümanı check edelim
        parser = argparse.ArgumentParser(description="Dashboard başlatıcı")
        parser.add_argument("--port", type=int, default=8000, help="Dashboard portu (varsayılan: 8000)")
        args, unknown = parser.parse_known_args()
        port = args.port
    
    print(f"Web dashboard başlatılıyor... (http://localhost:{port})")
    # Uvicorn ile app/api/main.py'deki FastAPI uygulamasını başlat
    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.api.main:app", "--reload", "--host", "0.0.0.0", "--port", str(port)
    ])

if __name__ == "__main__":
    run_dashboard() 