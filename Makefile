.PHONY: test clean lint install

# Değişkenler
PYTHON = python
TEST_DIR = tests
LINT_DIR = bot config database

# Varsayılan komut
all: clean test

# Test çalıştırma
test:
    pytest $(TEST_DIR)

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
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.eggs" -exec rm -rf {} +
    find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Linting
lint:
    pylint $(LINT_DIR)

# Bağımlılıkları yükleme
install:
    pip install -r requirements.txt

# Testler için gerekli bağımlılıkları yükleme
install-test:
    pip install pytest pytest-asyncio colorama tabulate python-dotenv