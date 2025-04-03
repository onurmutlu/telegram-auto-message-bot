#!/usr/bin/env python
import sys
import os

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ana modülü içe aktar ve çalıştır
from bot import main

if __name__ == "__main__":
    main.run()
