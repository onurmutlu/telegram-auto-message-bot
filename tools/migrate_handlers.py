#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: migrate_handlers.py
# Yol: /Users/siyahkare/code/telegram-bot/migrate_handlers.py
# İşlev: Legacy kod taşıma ve modernizasyon aracı
#
# Build: 2025-03-31-23:10:45
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu script, legacy_handlers klasöründeki eski kodları analiz eder ve 
# bot/handlers klasörüne modernize ederek taşır.
#
# - Kullanılmayan kodları tespit eder
# - Asenkron olmayan kodu asenkron hale getirir
# - Hata yönetimini ve log işlemlerini ekler
# - Dosya header'larını standartlaştırır
#
# Kullanım: python migrate_handlers.py
# ============================================================================ #
"""
import os
import sys
import re
import shutil
import datetime
import logging
import argparse
from pathlib import Path

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("migrate_handlers")

# Sabitler
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
LEGACY_DIR = PROJECT_ROOT / "legacy_handlers"
TARGET_DIR = PROJECT_ROOT / "bot" / "handlers"
BUILD_TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
VERSION = "v3.4.0"

class HandlerMigrator:
    def __init__(self, legacy_dir=LEGACY_DIR, target_dir=TARGET_DIR):
        self.legacy_dir = Path(legacy_dir)
        self.target_dir = Path(target_dir)
        self.migrated_files = []
        self.skipped_files = []
        self.modernized_changes = {}
        
        # Dış bağımlılıkları tespit etmek için
        self.dependency_graph = {}
        
    def validate_directories(self):
        """Klasör yapılarını kontrol eder ve hazırlar"""
        if not self.legacy_dir.exists():
            logger.error(f"Legacy klasörü bulunamadı: {self.legacy_dir}")
            return False
        
        # Target klasörü yoksa oluştur
        if not self.target_dir.exists():
            logger.info(f"Hedef klasör oluşturuluyor: {self.target_dir}")
            self.target_dir.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def list_legacy_handlers(self):
        """Legacy klasöründeki Python dosyalarını listeler"""
        py_files = []
        
        try:
            for file in self.legacy_dir.glob("**/*.py"):
                if file.is_file():
                    py_files.append(file)
        except Exception as e:
            logger.error(f"Dosyalar listelenirken hata: {e}")
        
        return py_files
    
    def analyze_file(self, file_path):
        """Dosyayı analiz eder ve modernizasyon ihtiyaçlarını tespit eder"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            analysis = {
                "has_async": "async def" in content,
                "imports": re.findall(r"import\s+([^\n;]+)|from\s+([^\s]+)\s+import", content),
                "has_error_handling": "try:" in content and "except" in content,
                "has_logging": "logging" in content or "logger" in content,
                "content": content,
                "needs_modernization": []
            }
            
            # Modernleştirme ihtiyaçlarını tespit et
            if not analysis["has_async"]:
                analysis["needs_modernization"].append("async_conversion")
            if not analysis["has_error_handling"]:
                analysis["needs_modernization"].append("error_handling")
            if not analysis["has_logging"]:
                analysis["needs_modernization"].append("logging")
            
            # Bağımlılık grafiği
            for imp in analysis["imports"]:
                dep = imp[0].strip() if imp[0] else imp[1].strip()
                if dep:
                    if file_path.name not in self.dependency_graph:
                        self.dependency_graph[file_path.name] = []
                    self.dependency_graph[file_path.name].append(dep)
            
            return analysis
        except Exception as e:
            logger.error(f"Dosya analiz edilirken hata ({file_path}): {e}")
            return None
    
    def modernize_code(self, file_path, analysis):
        """Kodu modernleştirir"""
        content = analysis["content"]
        changes = []
        
        # 1. Asenkron dönüşümü
        if "async_conversion" in analysis["needs_modernization"]:
            # Basit fonksiyonları async'e çevir
            new_content = re.sub(
                r"def\s+([a-zA-Z0-9_]+)\((.*?)\):",
                r"async def \1(\2):",
                content
            )
            
            # Uzun tür cevrimini gerekiyorsa işaretleyelim
            if content != new_content:
                changes.append("🔄 Fonksiyonlar asenkron hale getirildi")
                content = new_content
        
        # 2. Hata yönetimi ekle
        if "error_handling" in analysis["needs_modernization"]:
            # Ana fonksiyonu bul ve try-except ile saral
            function_pattern = r"(async\s+)?def\s+([a-zA-Z0-9_]+)\((.*?)\):(.*?)(?=\n\S|\Z)"
            
            def wrap_with_try_except(match):
                prefix, func_name, params, body = match.groups()
                prefix = prefix or ""
                indented_body = body.replace("\n", "\n    ")
                
                new_body = f"\n    try:{indented_body}\n    except Exception as e:\n        logger.error(\"Error in {0}: {1}\".format(func_name, str(e)))\n        raise\n"
                return f"{prefix}def {func_name}({params}):{new_body}"
            
            new_content = re.sub(function_pattern, wrap_with_try_except, content, flags=re.DOTALL)
            
            if content != new_content:
                changes.append("🛡️ Hata yönetimi eklendi")
                content = new_content
        
        # 3. Loglama ekle
        if "logging" in analysis["needs_modernization"]:
            # İmport kısmını bul
            import_section = re.search(r"(import.*?)(?=\n\n|\n[^i\s]|\Z)", content, re.DOTALL)
            
            if import_section:
                import_end = import_section.end()
                if "logging" not in content[:import_end]:
                    log_setup = "\nimport logging\n\nlogger = logging.getLogger(__name__)\n"
                    content = content[:import_end] + log_setup + content[import_end:]
                    changes.append("📝 Loglama eklendi")
        
        # 4. Header ekle
        content = self.add_standardized_header(file_path.name, content)
        changes.append("📄 Standart header eklendi")
        
        return content, changes
    
    def add_standardized_header(self, filename, content):
        """Standart header ekler"""
        # Mevcut docstring'i kaldır
        content = re.sub(r'^"""[\s\S]*?"""', '', content).strip()
        
        # Yeni header oluştur
        header = [
            '"""',
            "# ============================================================================ #",
            f"# Dosya: {filename}",
            f"# Yol: {self.target_dir / filename}",
            "# İşlev: Telegram bot mesaj işleyicisi",
            "#",
            f"# Build: {BUILD_TIMESTAMP}",
            f"# Versiyon: {VERSION}",
            "# ============================================================================ #",
            "#",
            "# Bu modül, Telegram mesajlarını işleyen handler fonksiyonlarını içerir.",
            "# - Gelen komutları işleme",
            "# - Otomatik yanıtlar ve yönlendirmeler",
            "# - Kullanıcı etkileşimlerini izleme",
            "#",
            "# ============================================================================ #",
            '"""'
        ]
        
        return '\n'.join(header) + '\n\n' + content
    
    def migrate_file(self, source_file, interactive=True):
        """Dosyayı analiz edip modernleştirerek hedef klasöre kopyalar"""
        target_file = self.target_dir / source_file.name
        
        # Dosya zaten varsa sor
        if target_file.exists() and interactive:
            answer = input(f"❓ {source_file.name} dosyası zaten mevcut. Üzerine yazılsın mı? (e/H): ")
            if answer.lower() != 'e':
                logger.info(f"⏭️ {source_file.name} taşıma işlemi atlandı.")
                self.skipped_files.append(source_file.name)
                return False
        
        # Dosyayı analiz et
        analysis = self.analyze_file(source_file)
        if not analysis:
            logger.error(f"❌ {source_file.name} dosyası analiz edilemedi.")
            self.skipped_files.append(source_file.name)
            return False
        
        # Modernizasyon gerekiyor mu?
        if interactive and analysis["needs_modernization"]:
            needs = ", ".join(analysis["needs_modernization"])
            answer = input(f"❓ {source_file.name} dosyası için modernizasyon gerekiyor ({needs}). Devam edilsin mi? (E/h): ")
            if answer.lower() == 'h':
                # Basit kopyalama
                shutil.copy2(source_file, target_file)
                logger.info(f"📋 {source_file.name} dosyası modernize edilmeden kopyalandı.")
                self.migrated_files.append(source_file.name)
                return True
        
        # Kodu modernleştir
        modern_content, changes = self.modernize_code(source_file, analysis)
        
        # Dosyayı hedef klasöre yaz
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(modern_content)
        
        # Modernizasyon değişikliklerini kaydet
        self.modernized_changes[source_file.name] = changes
        
        logger.info(f"✅ {source_file.name} dosyası modernize edilerek taşındı.")
        self.migrated_files.append(source_file.name)
        return True
    
    def generate_report(self):
        """Taşıma işlemi raporunu oluşturur"""
        report = [
            "# Legacy Handlers Taşıma Raporu",
            f"Tarih: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Özet",
            f"- Toplam taşınan dosya: {len(self.migrated_files)}",
            f"- Atlanan dosya: {len(self.skipped_files)}",
            ""
        ]
        
        if self.migrated_files:
            report.append("## Taşınan Dosyalar")
            for filename in self.migrated_files:
                report.append(f"### {filename}")
                if filename in self.modernized_changes:
                    report.append("Yapılan değişiklikler:")
                    for change in self.modernized_changes[filename]:
                        report.append(f"- {change}")
                report.append("")
        
        if self.skipped_files:
            report.append("## Atlanan Dosyalar")
            for filename in self.skipped_files:
                report.append(f"- {filename}")
            report.append("")
        
        if self.dependency_graph:
            report.append("## Bağımlılık Analizi")
            for file, deps in self.dependency_graph.items():
                report.append(f"### {file}")
                report.append("Bağımlılıklar:")
                for dep in deps:
                    report.append(f"- {dep}")
                report.append("")
        
        # Raporu dosyaya yaz
        report_path = PROJECT_ROOT / "migration_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        logger.info(f"📊 Taşıma raporu oluşturuldu: {report_path}")
    
    def handle_legacy_directory(self, action="archive"):
        """Legacy klasörünü yönetir"""
        if action == "archive":
            archive_path = self.legacy_dir.parent / f"legacy_handlers_archive_{datetime.datetime.now().strftime('%Y%m%d')}"
            shutil.move(str(self.legacy_dir), str(archive_path))
            logger.info(f"📦 Legacy klasörü arşivlendi: {archive_path}")
            
            # Arşive README ekle
            readme_path = archive_path / "README.md"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Arşivlenmiş Legacy Handlers
                
Bu klasör, v{VERSION} sürümünde modernize edilerek `bot/handlers` klasörüne taşınan eski kodları içerir.
Arşivlenme tarihi: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Bu kodlar artık kullanılmamaktadır ve sadece referans amaçlıdır.
                """)
        
        elif action == "delete":
            shutil.rmtree(self.legacy_dir)
            logger.info(f"🗑️ Legacy klasörü silindi: {self.legacy_dir}")
    
    def run(self, interactive=True, exclude=None):
        """Taşıma işlemini çalıştırır"""
        logger.info("🚀 Legacy handlers taşıma işlemi başlatılıyor...")
        
        # Klasörleri kontrol et
        if not self.validate_directories():
            return False
        
        # Dosyaları listele
        legacy_files = self.list_legacy_handlers()
        if not legacy_files:
            logger.warning("⚠️ Legacy klasöründe Python dosyası bulunamadı.")
            return False
        
        # Hariç tutulan dosyaları filtrele
        if exclude:
            legacy_files = [f for f in legacy_files if f.name not in exclude]
        
        # Tüm dosyaları işle
        for file in legacy_files:
            logger.info(f"🔍 {file.name} dosyası işleniyor...")
            
            if interactive:
                answer = input(f"❓ {file.name} dosyası taşınsın mı? (E/h): ")
                if answer.lower() == 'h':
                    logger.info(f"⏭️ {file.name} taşıma işlemi atlandı.")
                    self.skipped_files.append(file.name)
                    continue
            
            self.migrate_file(file, interactive)
        
        # Rapor oluştur
        self.generate_report()
        
        logger.info(f"✨ Taşıma işlemi tamamlandı! {len(self.migrated_files)} dosya taşındı, {len(self.skipped_files)} dosya atlandı.")
        return True

def main():
    parser = argparse.ArgumentParser(description="Legacy handler kodlarını modernize ederek taşır")
    parser.add_argument("--non-interactive", action="store_true", help="Etkileşimli olmadan çalıştır (tüm dosyaları modernize ederek taşır)")
    parser.add_argument("--exclude", nargs="*", help="Taşıma işleminden hariç tutulacak dosyalar")
    
    args = parser.parse_args()
    
    migrator = HandlerMigrator()
    migrator.run(interactive=not args.non_interactive, exclude=args.exclude)

if __name__ == "__main__":
    main()