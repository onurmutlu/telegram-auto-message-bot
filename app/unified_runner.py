#!/usr/bin/env python3
"""
Birleştirilmiş bot sistemini başlatma scripti.
Unified klasöründeki run.py dosyasına parametreleri aktarır.
"""

import sys
import os
import subprocess

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    # Script dizinini bul
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Unified dizini kontrol et ve oluştur (yoksa)
    unified_dir = os.path.join(script_dir, "unified")
    if not os.path.exists(unified_dir):
        os.makedirs(unified_dir, exist_ok=True)
        print(f"Unified dizini oluşturuldu: {unified_dir}")
    
    # run.py dosyasının yolunu al
    run_script = os.path.join(unified_dir, "run.py")
    
    # Script dosyasının varlığını kontrol et
    if not os.path.exists(run_script):
        print(f"Hata: {run_script} dosyası bulunamadı!")
        # Temel bir run.py dosyası oluştur
        with open(run_script, 'w') as f:
            f.write("""#!/usr/bin/env python3
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
""")
        print(f"Temel bir {run_script} dosyası oluşturuldu.")
        os.chmod(run_script, 0o755)  # Çalıştırma izni ver
    
    # Script'i çalıştırılabilir yap
    try:
        os.chmod(run_script, 0o755)
    except Exception as e:
        print(f"Uyarı: Çalıştırma izni verilemedi: {str(e)}")
    
    # Parametreleri geçir
    command = [sys.executable, run_script] + sys.argv[1:]
    
    try:
        # Çalıştır
        subprocess.run(command)
    except Exception as e:
        print(f"Hata: Komut çalıştırılamadı: {str(e)}")
        # Doğrudan main.py dosyasını çalıştırmayı dene
        main_script = os.path.join(unified_dir, "main.py")
        if os.path.exists(main_script):
            print(f"Ana modülü doğrudan çalıştırmayı deniyorum: {main_script}")
            subprocess.run([sys.executable, main_script] + sys.argv[1:])
        else:
            print(f"Kritik hata: {main_script} bulunamadı!")

if __name__ == "__main__":
    main() 