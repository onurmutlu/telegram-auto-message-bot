#!/usr/bin/env python3
"""
Bot başlatma scripti.
Bu script, tek bir noktadan bot'u farklı modlarda başlatmak için kullanılır.
"""

import sys
import os
import argparse
import subprocess

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Ana fonksiyon"""
    parser = argparse.ArgumentParser(description="Telegram Bot Başlatıcı")
    
    # Çalıştırma modu
    parser.add_argument("--mode", choices=["local", "docker", "docker-compose"], 
                      default="local", help="Çalıştırma modu")
    
    # Bot parametreleri
    parser.add_argument("--debug", action="store_true", help="Debug modunu etkinleştirir")
    parser.add_argument("--clean", action="store_true", help="Başlamadan önce temizlik yapar")
    parser.add_argument("--config", help="Belirli bir yapılandırma dosyası kullanır")
    parser.add_argument("--service", help="Belirli bir servisi başlatır (grup, mesaj, davet)")
    
    # Docker özel parametreler
    parser.add_argument("--build", action="store_true", help="Docker imajını yeniden oluşturur")
    parser.add_argument("--detach", "-d", action="store_true", help="Arkaplanda çalıştırır")
    
    args = parser.parse_args()
    
    # Proje kök dizini
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)
    
    # Unified dizini
    unified_dir = os.path.join(root_dir, "unified")
    
    # Bot parametreleri oluştur
    bot_params = []
    if args.debug:
        bot_params.append("--debug")
    if args.clean:
        bot_params.append("--clean")
    if args.config:
        bot_params.append(f"--config={args.config}")
    if args.service:
        bot_params.append(f"--service={args.service}")
    
    if args.mode == "local":
        # Yerel modda çalıştır
        print("Bot yerel modda başlatılıyor...")
        cmd = [sys.executable, os.path.join(unified_dir, "main.py")] + bot_params
        subprocess.run(cmd)
        
    elif args.mode == "docker":
        # Docker ile çalıştır
        print("Bot Docker modunda başlatılıyor...")
        docker_cmd = ["docker", "run"]
        
        if args.build:
            # Önce build
            print("Docker imajı oluşturuluyor...")
            build_cmd = ["docker", "build", "-t", "telegram-bot", "-f", os.path.join(unified_dir, "Dockerfile"), "."]
            subprocess.run(build_cmd)
        
        # Docker run parametreleri
        if args.detach:
            docker_cmd.append("-d")
        
        # Çevre değişkenleri
        from dotenv import load_dotenv
        load_dotenv()
        env_vars = ["API_ID", "API_HASH", "DATABASE_URL", "BOT_TOKEN", 
                   "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", 
                   "POSTGRES_USER", "POSTGRES_PASSWORD"]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                docker_cmd.extend(["-e", f"{var}={value}"])
        
        # Gerekli dizinleri bağla
        docker_cmd.extend([
            "-v", f"{os.path.join(root_dir, 'data')}:/app/data",
            "-v", f"{os.path.join(root_dir, 'logs')}:/app/logs",
            "-v", f"{os.path.join(root_dir, 'session')}:/app/session",
            "-v", f"{os.path.join(root_dir, 'runtime')}:/app/runtime"
        ])
        
        # İmaj adı
        docker_cmd.append("telegram-bot")
        
        # Bot parametreleri
        if bot_params:
            docker_cmd.extend(bot_params)
            
        # Çalıştır
        subprocess.run(docker_cmd)
        
    elif args.mode == "docker-compose":
        # Docker Compose ile çalıştır
        print("Bot Docker Compose modunda başlatılıyor...")
        compose_file = os.path.join(unified_dir, "docker-compose.yml")
        
        compose_cmd = ["docker-compose", "-f", compose_file]
        
        if args.build:
            compose_cmd.append("build")
            subprocess.run(compose_cmd)
            compose_cmd = ["docker-compose", "-f", compose_file]
        
        if args.detach:
            compose_cmd.extend(["up", "-d"])
        else:
            compose_cmd.append("up")
            
        # Çalıştır
        subprocess.run(compose_cmd)
    
if __name__ == "__main__":
    main() 