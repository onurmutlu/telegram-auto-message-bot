#!/usr/bin/env python3
import sys
import os
import subprocess

# Ana dizine geç
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(script_dir)

# Ana modülü çalıştır
main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
if os.path.exists(main_script):
    sys.argv[0] = main_script
    subprocess.run([sys.executable, main_script] + sys.argv[1:])
else:
    print(f"Hata: {main_script} dosyası bulunamadı!")
    sys.exit(1)
