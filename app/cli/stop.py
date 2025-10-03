"""
Bot durdurma komutları
"""
import os
import sys
import signal
import logging
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

async def stop_bot():
    """Bot proseslerini durdurur"""
    try:
        # PID dosyasını kontrol et
        pid_file = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / ".bot_pids"
        
        if not pid_file.exists():
            logger.error("Bot çalışmıyor veya PID dosyası bulunamadı.")
            return False, "Bot çalışmıyor."
        
        # PID'leri oku
        with open(pid_file, "r") as f:
            pids = [line.strip() for line in f.readlines() if line.strip()]
        
        if not pids:
            logger.error("Bot çalışmıyor (PID dosyası boş).")
            return False, "Bot çalışmıyor."
        
        # Tüm prosesleri durdur
        stopped_pids = []
        failed_pids = []
        
        for pid in pids:
            try:
                # Proses durumunu kontrol et ve sinyali gönder
                pid_int = int(pid)
                
                # Unix sistemlerinde
                if os.name == 'posix':
                    try:
                        os.kill(pid_int, signal.SIGTERM)
                        stopped_pids.append(pid)
                        logger.info(f"PID {pid} için SIGTERM sinyali gönderildi.")
                    except ProcessLookupError:
                        logger.warning(f"PID {pid} bulunamadı, zaten sonlandırılmış olabilir.")
                        stopped_pids.append(pid)
                    except PermissionError:
                        logger.error(f"PID {pid} için yeterli izin yok.")
                        failed_pids.append(pid)
                    except Exception as e:
                        logger.error(f"PID {pid} sonlandırılırken hata: {e}")
                        failed_pids.append(pid)
                
                # Windows sistemlerinde
                elif os.name == 'nt':
                    import ctypes
                    handle = ctypes.windll.kernel32.OpenProcess(1, False, pid_int)
                    if handle:
                        result = ctypes.windll.kernel32.TerminateProcess(handle, 0)
                        ctypes.windll.kernel32.CloseHandle(handle)
                        if result:
                            stopped_pids.append(pid)
                            logger.info(f"PID {pid} sonlandırıldı.")
                        else:
                            failed_pids.append(pid)
                            logger.error(f"PID {pid} sonlandırılamadı.")
                    else:
                        logger.warning(f"PID {pid} bulunamadı, zaten sonlandırılmış olabilir.")
                        stopped_pids.append(pid)
                
            except Exception as e:
                logger.error(f"PID {pid} işlenirken hata: {e}")
                failed_pids.append(pid)
        
        # PID dosyasını temizle
        if not failed_pids:
            if os.path.exists(pid_file):
                os.remove(pid_file)
            logger.info("PID dosyası temizlendi.")
        else:
            # Başarısız PID'ler hariç diğerlerini temizle
            with open(pid_file, "w") as f:
                f.write("\n".join(failed_pids))
            logger.warning("Bazı PID'ler durdurulamadı, PID dosyası güncellendi.")
        
        if stopped_pids:
            message = f"Bot durduruldu. Sonlandırılan PID'ler: {', '.join(stopped_pids)}"
            if failed_pids:
                message += f" (Durdurulamayan PID'ler: {', '.join(failed_pids)})"
            logger.info(message)
            return True, message
        else:
            message = "Bot durdurulamadı."
            if failed_pids:
                message += f" (Durdurulamayan PID'ler: {', '.join(failed_pids)})"
            logger.error(message)
            return False, message
        
    except Exception as e:
        logger.error(f"Bot durdurma işlemi sırasında hata: {e}")
        return False, f"Hata: {str(e)}"

def run_stop():
    """CLI için stop çalıştırıcı"""
    result, message = asyncio.run(stop_bot())
    
    if result:
        print("\033[92m" + message + "\033[0m")  # Yeşil
    else:
        print("\033[91m" + message + "\033[0m")  # Kırmızı
    
    return result 