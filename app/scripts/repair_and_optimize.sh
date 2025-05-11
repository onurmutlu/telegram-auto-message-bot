#!/bin/bash
#
# Telegram botunu otomatik olarak onarır ve optimize eder
# 1. Telethon oturum dosyalarını düzeltir
# 2. Veritabanı şemasını günceller
# 3. Data mining tablolarını düzeltir
# 4. Botu yeniden başlatır
#
# Kullanım: bash repair_and_optimize.sh [--no-restart]
#

# Renk değişkenleri
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log fonksiyonu
log_info() {
    echo -e "${BLUE}[$(date +"%Y-%m-%d %H:%M:%S")] INFO${NC}: $1"
}

log_success() {
    echo -e "${GREEN}[$(date +"%Y-%m-%d %H:%M:%S")] SUCCESS${NC}: $1"
}

log_error() {
    echo -e "${RED}[$(date +"%Y-%m-%d %H:%M:%S")] ERROR${NC}: $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +"%Y-%m-%d %H:%M:%S")] WARNING${NC}: $1"
}

# Parametreleri işle
NO_RESTART=false
for arg in "$@"; do
    case $arg in
        --no-restart)
            NO_RESTART=true
            shift
            ;;
    esac
done

# Ana çalışma dizini
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR" || { log_error "Proje dizinine geçilemedi"; exit 1; }

log_info "📋 Bot onarım ve optimizasyon süreci başlatılıyor..."
log_info "📂 Proje dizini: $PROJECT_DIR"

# Gerekli Python kütüphanelerini kontrol et ve yükle
check_and_install_modules() {
    log_info "📦 Gerekli Python modülleri kontrol ediliyor..."
    
    # İhtiyaç duyulan modüller
    required_modules=("asyncpg" "psycopg2-binary" "telethon" "python-dotenv")
    
    for module in "${required_modules[@]}"; do
        if ! python -c "import $module" &>/dev/null; then
            log_warning "⚠️ '$module' modülü bulunamadı, yükleniyor..."
            pip install "$module"
            if [ $? -eq 0 ]; then
                log_success "✅ '$module' başarıyla yüklendi"
            else
                log_error "❌ '$module' yüklenemedi"
            fi
        else
            log_info "✓ '$module' zaten yüklü"
        fi
    done
}

# Çalışan bot sürecini kontrol et
check_running_bot() {
    if pgrep -f "python.*bot.main" >/dev/null; then
        log_warning "⚠️ Bot çalışıyor, önce durduruluyor..."
        pkill -f "python.*bot.main"
        sleep 2
        
        # Hala çalışıyorsa zorla sonlandır
        if pgrep -f "python.*bot.main" >/dev/null; then
            log_warning "⚠️ Bot normal şekilde durdurulamadı, zorla sonlandırılıyor..."
            pkill -9 -f "python.*bot.main"
            sleep 1
        fi
        
        log_success "✅ Bot durduruldu"
    else
        log_info "ℹ️ Çalışan bot süreci bulunamadı, devam ediliyor."
    fi
}

# Tüm düzeltme scriptlerini çalıştır
run_fix_scripts() {
    log_info "🔧 Tüm düzeltme scriptleri çalıştırılıyor..."
    
    # fix_all.py scriptini çalıştır
    python "$SCRIPT_DIR/fix_all.py"
    if [ $? -eq 0 ]; then
        log_success "✅ Düzeltme scriptleri başarıyla çalıştırıldı."
    else
        log_warning "⚠️ Düzeltme scriptleri çalıştırılırken bazı hatalar oluştu."
    fi
    
    # Kalıcı Telethon oturum düzeltme scriptini çalıştır
    log_info "🔧 Telethon oturum dosyalarını kalıcı olarak düzeltme..."
    python "$SCRIPT_DIR/fix_telethon_session_permanent.py"
    if [ $? -eq 0 ]; then
        log_success "✅ Telethon oturum dosyaları kalıcı olarak düzeltildi."
    else
        log_warning "⚠️ Telethon oturum dosyaları düzeltilirken bazı hatalar oluştu."
    fi
}

# Telethon oturum dosyalarını optimize et (VACUUM)
optimize_sessions() {
    log_info "🔧 Telethon session dosyaları vakumlanıyor..."
    
    # Session dosyalarını bul
    SESSION_FILES=$(find "$PROJECT_DIR" -name "*.session" -type f)
    
    # Her dosya için sqlite3 VACUUM komutu çalıştır
    for session_file in $SESSION_FILES; do
        if [ -f "$session_file" ]; then
            sqlite3 "$session_file" "VACUUM;"
        fi
    done
    
    log_success "✅ Session dosyaları başarıyla vakumlandı."
}

# Botu yeniden başlat
restart_bot() {
    if [ "$NO_RESTART" = true ]; then
        log_info "🚫 Bot yeniden başlatılmayacak (--no-restart parametresi kullanıldı)"
        return
    fi
    
    log_info "🚀 Bot yeniden başlatılıyor..."
    
    # Python virtual environment kontrolü
    if [ -d "$PROJECT_DIR/.venv" ] || [ -d "$PROJECT_DIR/venv" ]; then
        LOG_DIR="$PROJECT_DIR/logs"
        mkdir -p "$LOG_DIR"
        
        # Bot'u arka planda başlat
        cd "$PROJECT_DIR" && python -m bot.main > "$LOG_DIR/bot.log" 2>&1 &
        BOT_PID=$!
        
        # PID'i kontrol et
        if ps -p $BOT_PID > /dev/null; then
            log_success "✅ Bot başarıyla başlatıldı (PID: $BOT_PID)"
            log_info "📝 Bot logları için: tail -f $LOG_DIR/bot.log"
        else
            log_error "❌ Bot başlatılamadı"
            log_info "📝 Hata logları için: cat $LOG_DIR/bot.log"
        fi
    else
        log_error "❌ Python virtual environment bulunamadı"
    fi
}

# Ana çalışma akışı
check_running_bot
check_and_install_modules
run_fix_scripts
optimize_sessions
restart_bot

log_success "🎉 Onarım ve optimizasyon süreci tamamlandı!" 