"""
# ============================================================================ #
# Dosya: message_utils.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/message_utils.py
# Açıklama: Telegram botu için mesaj işleme yardımcı fonksiyonları.
#
# Amaç: Mesajlardaki metinleri temizleme, anahtar kelime kontrolü yapma ve diğer metin işleme görevlerini kolaylaştırma.
#
# Build: 2025-04-01-02:45:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, botun mesajları analiz etmesi ve işlemesi için çeşitli yardımcı fonksiyonlar içerir.
# Temel özellikleri:
# - Metin temizleme (URL'ler, mention'lar, hashtag'ler)
# - Anahtar kelime varlığını kontrol etme (tekil ve çoğul)
# - Büyük/küçük harf duyarsız arama
# - Hızlı ve etkili metin işleme
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

def check_keyword(keyword, text):
    """
    Verilen metinde bir anahtar kelimenin olup olmadığını kontrol eder (büyük/küçük harf duyarsız).

    Args:
        keyword (str): Aranacak anahtar kelime.
        text (str): İçinde arama yapılacak metin.

    Returns:
        bool: Anahtar kelime metinde bulunuyorsa True, aksi halde False.
    """
    return keyword.lower() in text.lower()

def check_keywords(keywords, text):
    """
    Verilen metinde anahtar kelimelerden herhangi birinin olup olmadığını kontrol eder (büyük/küçük harf duyarsız).

    Args:
        keywords (list): Aranacak anahtar kelimelerin listesi.
        text (str): İçinde arama yapılacak metin.

    Returns:
        bool: Anahtar kelimelerden herhangi biri metinde bulunuyorsa True, aksi halde False.
    """
    text = clean_text(text)
    return any(keyword.lower() in text for keyword in keywords)

def clean_text(text):
    """
    Verilen metinden URL'leri, mention'ları ve hashtag'leri temizler.

    Args:
        text (str): Temizlenecek metin.

    Returns:
        str: Temizlenmiş metin.
    """
    import re
    text = re.sub(r'http\S+|www\S+|@\S+|#\S+', '', text, flags=re.MULTILINE)
    return text.strip().lower()
