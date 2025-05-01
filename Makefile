.PHONY: test clean lint install run run-clean clean-logs clean-cache help migrate update_env setup_pg test_pg_connection test-pg full-migrate

# Değişkenler
PYTHON = python
TEST_DIR = tests
LINT_DIR = bot config database

# Varsayılan komut
all: clean test

# Test çalıştırma
test:
    @echo "🧪 Testler çalıştırılıyor..."
    python -m pytest

# Verbose test çalıştırma 
test-v:
    pytest -v $(TEST_DIR)

# Belirli bir testi çalıştırma
test-module:
    @read -p "Test modülü adı (örn: user_db): " module; \
    pytest -v $(TEST_DIR)/test_$$module.py

# İlk hatada duran test
test-fail-fast:
    pytest -xvs $(TEST_DIR)

# Temizleme
clean:
    @echo "🧹 Temizlik yapılıyor..."
    python cleanup.py --all
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.eggs" -exec rm -rf {} +
    find . -type d -name ".pytest_cache" -exec rm -rf {} +

clean-logs:
    @echo "📝 Loglar temizleniyor..."
    python cleanup.py --logs

clean-cache:
    @echo "📁 Cache dosyaları temizleniyor..."
    python cleanup.py --cache

# Linting
lint:
    pylint $(LINT_DIR)

# Bağımlılıkları yükleme
install:
    pip install -r requirements.txt

# Testler için gerekli bağımlılıkları yükleme
install-test:
    pip install pytest pytest-asyncio colorama tabulate python-dotenv

run:
    @echo "🤖 Bot başlatılıyor..."
    python main.py

run-clean: clean
    @echo "🤖 Temizlik sonrası bot başlatılıyor..."
    python main.py

# Veritabanı geçiş komutları

help:
	@echo "Telegram Bot PostgreSQL Geçiş Komutları"
	@echo "---------------------------------"
	@echo "migrate               : SQLite'dan PostgreSQL'e veri taşıma işlemini başlatır"
	@echo "update_env            : .env dosyasını PostgreSQL için günceller"
	@echo "setup_pg              : PostgreSQL bağlantısını ayarlar ve tabloları oluşturur"
	@echo "test_pg_connection    : PostgreSQL bağlantısını test eder"
	@echo "update_user_activities: Kullanıcı aktivite loglarını günceller"

migrate:
	@echo "SQLite'dan PostgreSQL'e veri taşınıyor..."
	python database/sqlite_to_postgres.py

update_env:
	@echo "PostgreSQL bağlantı bilgileri .env dosyasına ekleniyor..."
	@if grep -q "POSTGRES_HOST" .env; then \
		echo "PostgreSQL bağlantı bilgileri zaten mevcut"; \
	else \
		echo "# PostgreSQL bağlantı bilgileri" >> .env; \
		echo "POSTGRES_HOST=localhost" >> .env; \
		echo "POSTGRES_PORT=5432" >> .env; \
		echo "POSTGRES_DB=telegram_bot" >> .env; \
		echo "POSTGRES_USER=postgres" >> .env; \
		echo "POSTGRES_PASSWORD=" >> .env; \
		echo "# Varsayılan bağlantı tipini PostgreSQL olarak ayarla" >> .env; \
		echo "DB_CONNECTION=postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(POSTGRES_DB)" >> .env; \
		echo ".env dosyası güncellendi"; \
	fi

setup_pg:
	@echo "PostgreSQL tabloları oluşturuluyor..."
	python -c "from database.db_connection import DatabaseConnectionManager; import asyncio; mgr = DatabaseConnectionManager(); asyncio.run(mgr.initialize())"

test_pg_connection:
	@echo "PostgreSQL bağlantısı test ediliyor..."
	python -c "import psycopg2; import os; from dotenv import load_dotenv; load_dotenv(); conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST', 'localhost'), port=os.getenv('POSTGRES_PORT', '5432'), dbname=os.getenv('POSTGRES_DB', 'telegram_bot'), user=os.getenv('POSTGRES_USER', 'postgres'), password=os.getenv('POSTGRES_PASSWORD', '')); print('Bağlantı başarılı!'); conn.close()"

test-pg:
	@echo "PostgreSQL veritabanı işlevlerini test ediliyor..."
	python test_pg_connection.py

update_user_activities:
	@echo "Kullanıcı aktivite logları güncelleniyor..."
	python update_user_activities.py

full-migrate: update_env test_pg_connection setup_pg migrate test-pg update_user_activities
	@echo "PostgreSQL'e tam geçiş tamamlandı!"
	@echo "Eski SQLite veritabanınızı yedeklemeyi unutmayın:"
	@echo "cp data/users.db data/users.db.bak"
	@echo ""
	@echo "PostgreSQL bağlantısını test etmek için:"
	@echo "make test-pg"