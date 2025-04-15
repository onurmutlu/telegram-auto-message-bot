"""
# ============================================================================ #
# Dosya: user_profiler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/user_profiler.py
# İşlev: Kullanıcı profillerini analiz eden ve segmente ayıran sistem.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Union

import aiohttp

# İsteğe bağlı importlar - bu kütüphaneler yüklü değilse çalışmayı sürdür
try:
    from scipy import spatial
    import numpy as np
    ADVANCED_ANALYTICS_AVAILABLE = True
except ImportError:
    ADVANCED_ANALYTICS_AVAILABLE = False
    logging.warning("Scipy/Numpy bulunamadı. Bazı gelişmiş analiz özellikleri devre dışı kalacak.")

logger = logging.getLogger(__name__)

class UserProfiler:
    """
    GPT ve TDLib kullanan gelişmiş kullanıcı profilleme sistemi.
    
    Bu sınıf:
    1. Kullanıcı mesajlarını analiz eder
    2. GPT API'yi kullanarak demografik bilgileri tahmin eder
    3. Kullanıcıları segmentlere ayırır
    4. Kişiselleştirilmiş yanıtlar için kullanıcı profili oluşturur
    """
    
    def __init__(self, db, config):
        """
        UserProfiler sınıfının başlatıcısı.
        
        Args:
            db: Veritabanı nesnesi
            config: Yapılandırma nesnesi
        """
        self.db = db
        self.config = config
        
        # GPT API bilgileri
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        self.api_model = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        # Önbellek
        self.profile_cache = {}
        self.message_history = {}
        self.embedding_cache = {}
        
        # Segmentler ve onların özellikleri
        self.segments = {
            'genç_erkek': {'yaş': 18, 'cinsiyet': 'erkek', 'ilgi': ['oyunlar', 'spor', 'teknoloji']},
            'genç_kadın': {'yaş': 18, 'cinsiyet': 'kadın', 'ilgi': ['moda', 'sosyal medya', 'müzik']},
            'orta_erkek': {'yaş': 35, 'cinsiyet': 'erkek', 'ilgi': ['kariyer', 'spor', 'teknoloji']},
            'orta_kadın': {'yaş': 35, 'cinsiyet': 'kadın', 'ilgi': ['yaşam tarzı', 'sağlık', 'yemek']},
            'olgun_erkek': {'yaş': 50, 'cinsiyet': 'erkek', 'ilgi': ['finans', 'seyahat', 'politika']},
            'olgun_kadın': {'yaş': 50, 'cinsiyet': 'kadın', 'ilgi': ['aile', 'sağlık', 'hobi']}
        }
        
        # Rate limiter
        self.last_call = 0
        self.min_call_interval = 3  # 3 saniye minimum aralık 
    
    async def analyze_user_message(self, user_id: int, message: str, 
                                 username: Optional[str] = None,
                                 first_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Kullanıcı mesajını analiz eder ve profil bilgilerini günceller.
        
        Args:
            user_id: Kullanıcı ID'si
            message: Mesaj metni
            username: Kullanıcı adı (opsiyonel)
            first_name: Kullanıcının adı (opsiyonel)
            
        Returns:
            Dict: Güncellenen profil bilgileri
        """
        if not message.strip():
            return {}
            
        # Kullanıcının mesaj geçmişini güncelle
        if user_id not in self.message_history:
            self.message_history[user_id] = []
            
        # Önceki 10 mesajı sakla
        self.message_history[user_id].append({
            'text': message,
            'time': datetime.now().isoformat()
        })
        
        if len(self.message_history[user_id]) > 10:
            self.message_history[user_id].pop(0)
            
        # Her mesajı analiz etmiyoruz, mesaj sayısına göre karar veriyoruz
        message_count = len(self.message_history[user_id])
        
        if message_count == 1:
            # İlk mesajda basit analiz yap
            profile = await self._basic_analyze(user_id, message, username, first_name)
            return profile
            
        elif message_count == 5 or message_count % 10 == 0:
            # 5. mesaj veya her 10 mesajda bir GPT ile analiz
            profile = await self._deep_analyze_with_gpt(user_id)
            
            # Profili veritabanına kaydet
            await self._save_profile_to_db(user_id, profile)
            return profile
            
        # Diğer durumlarda önbellekteki profili dön
        return self.profile_cache.get(user_id, {})
    
    async def _basic_analyze(self, user_id: int, message: str, 
                            username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
        """
        Basit profil analizi yapar.
        
        Args:
            user_id: Kullanıcı ID'si
            message: Mesaj metni
            username: Kullanıcı adı (opsiyonel)
            first_name: Kullanıcının adı (opsiyonel)
            
        Returns:
            Dict: Basit profil bilgileri
        """
        # Veritabanından mevcut profil varsa yükle
        profile = await self._load_profile_from_db(user_id)
        if profile:
            self.profile_cache[user_id] = profile
            return profile
            
        # Yeni bir profil oluştur
        profile = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'messages_analyzed': 1,
            'last_updated': datetime.now().isoformat(),
            'created_at': datetime.now().isoformat()
        }
        
        # Cinsiyet tahmini (İsim temelli basit kural)
        if first_name:
            # Türkçe kadın isim sonları
            female_suffixes = ['a', 'e', 'n', 'y', 'han', 'can']
            # Kadın ismi olabilecek özellikleri kontrol et
            if any(first_name.lower().endswith(suffix) for suffix in female_suffixes):
                profile['gender_guess'] = 'kadın'
                profile['gender_confidence'] = 0.6
            else:
                profile['gender_guess'] = 'erkek'
                profile['gender_confidence'] = 0.6
        
        # Profili önbelleğe al
        self.profile_cache[user_id] = profile
        
        # Profili veritabanına kaydet
        await self._save_profile_to_db(user_id, profile)
        
        return profile
    
    async def _deep_analyze_with_gpt(self, user_id: int) -> Dict[str, Any]:
        """
        GPT API kullanarak kullanıcının mesajlarını derin analiz eder.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Dict: Kapsamlı profil bilgileri
        """
        if user_id not in self.message_history or not self.message_history[user_id]:
            return self.profile_cache.get(user_id, {})
            
        # Mevcut profili yükle
        current_profile = self.profile_cache.get(user_id, {})
        
        # Kullanıcının mesajlarını bir araya getir
        messages = self.message_history[user_id]
        message_texts = [m['text'] for m in messages]
        combined_text = "\n".join(message_texts)
        
        # GPT için prompt hazırla
        prompt = f"""
        Aşağıdaki mesajları gönderen kullanıcının profilini analiz et:
        
        ---
        {combined_text}
        ---
        
        Analiz et ve aşağıdaki bilgileri JSON formatında ver:
        1. Tahmini yaş aralığı (min-max): 18-24, 25-34, 35-44, 45-54, 55+
        2. Tahmini cinsiyet ve eminlik değeri (0-1 arası): erkek/kadın
        3. İlgi alanları (en az 3 tane)
        4. Tahmini demografik grup: öğrenci, profesyonel, ev hanımı/erkeği, emekli, girişimci
        5. İletişim stili: resmi, samimi, profesyonel, flörtöz, soğuk, arkadaşça
        
        Sadece JSON formatında yanıt ver. JSON'dan önce veya sonra hiçbir şey yazma.
        """
        
        try:
            # Rate limiter
            current_time = time.time()
            time_diff = current_time - self.last_call
            if time_diff < self.min_call_interval:
                # Minimum aralık geçene kadar bekle
                await asyncio.sleep(self.min_call_interval - time_diff)
                
            # GPT API isteği
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.api_model,
                "messages": [
                    {"role": "system", "content": "Sen bir kullanıcı profil analiz uzmanısın. Verilen mesajlara bakarak kişinin demografik özelliklerini tahmin ediyorsun."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            # API çağrısı
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    self.last_call = time.time()  # Son çağrı zamanını güncelle
                    
                    if response.status != 200:
                        logger.error(f"GPT API hatası: {response.status}, {await response.text()}")
                        return current_profile
                        
                    data = await response.json()
                    api_response = data['choices'][0]['message']['content']
            
            # Yanıtı JSON olarak ayrıştır
            try:
                # JSON formatını temizle
                api_response = api_response.replace("```json", "").replace("```", "").strip()
                gpt_profile = json.loads(api_response)
                
                # Mevcut profili güncelle
                current_profile.update({
                    'age_range': gpt_profile.get('yaş aralığı', '25-34'),
                    'gender_guess': gpt_profile.get('cinsiyet', current_profile.get('gender_guess', 'erkek')),
                    'gender_confidence': gpt_profile.get('eminlik', 0.7),
                    'interests': gpt_profile.get('ilgi alanları', []),
                    'demographic_group': gpt_profile.get('demografik grup', 'profesyonel'),
                    'communication_style': gpt_profile.get('iletişim stili', 'arkadaşça'),
                    'messages_analyzed': len(messages),
                    'last_updated': datetime.now().isoformat(),
                })
                
                # Segment belirle
                current_profile['segment'] = self._determine_segment(current_profile)
                
                # Profili önbelleğe kaydet
                self.profile_cache[user_id] = current_profile
                
                logger.info(f"Kullanıcı {user_id} için GPT profil analizi tamamlandı")
                return current_profile
                
            except json.JSONDecodeError as e:
                logger.error(f"GPT yanıtı JSON olarak ayrıştırılamadı: {str(e)}, yanıt: {api_response}")
                return current_profile
                
        except Exception as e:
            logger.error(f"GPT analizi sırasında hata: {str(e)}")
            return current_profile
    
    def _determine_segment(self, profile: Dict[str, Any]) -> str:
        """
        Kullanıcı segmentini belirler.
        
        Args:
            profile: Kullanıcı profili
            
        Returns:
            str: Segment adı
        """
        # Yaş aralığını analiz et
        age_range = profile.get('age_range', '25-34')
        try:
            min_age, max_age = map(int, age_range.split('-'))
            avg_age = (min_age + max_age) / 2
        except ValueError:
            avg_age = 30  # Varsayılan
            
        # Yaş grubunu belirle
        if avg_age < 25:
            age_group = 'genç'
        elif avg_age < 45:
            age_group = 'orta'
        else:
            age_group = 'olgun'
            
        # Cinsiyet
        gender = profile.get('gender_guess', 'erkek').lower()
        gender = 'erkek' if gender == 'male' else 'kadın' if gender == 'female' else gender
        
        # Segmenti birleştir
        segment = f"{age_group}_{gender}"
        
        # Eğer segment tanımlıysa döndür, yoksa genel segment
        return segment if segment in self.segments else 'genel'
    
    async def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Kullanıcının profilini döndürür, gerekirse veritabanından yükler.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Dict: Kullanıcı profil bilgileri
        """
        # Önbellekte var mı kontrol et
        if user_id in self.profile_cache:
            return self.profile_cache[user_id]
            
        # Veritabanından yükle
        profile = await self._load_profile_from_db(user_id)
        
        if profile:
            self.profile_cache[user_id] = profile
            return profile
            
        # Boş profil
        return {}
    
    async def _load_profile_from_db(self, user_id: int) -> Dict[str, Any]:
        """
        Veritabanından kullanıcı profilini yükler.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            Dict: Kullanıcı profili veya boş sözlük
        """
        try:
            if hasattr(self.db, 'get_user_profile'):
                profile = await self._run_async_db_method(self.db.get_user_profile, user_id)
                return profile or {}
        except Exception as e:
            logger.error(f"Kullanıcı profili yüklenirken hata: {str(e)}")
        
        return {}
    
    async def _save_profile_to_db(self, user_id: int, profile: Dict[str, Any]) -> bool:
        """
        Kullanıcı profilini veritabanına kaydeder.
        
        Args:
            user_id: Kullanıcı ID'si
            profile: Kullanıcı profil bilgileri
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            if hasattr(self.db, 'update_user_profile'):
                await self._run_async_db_method(self.db.update_user_profile, user_id, profile)
                return True
        except Exception as e:
            logger.error(f"Kullanıcı profili kaydedilirken hata: {str(e)}")
        
        return False
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: method(*args, **kwargs)
        )
    
    def get_recommended_approach(self, user_id: int) -> str:
        """
        Kullanıcıya yaklaşma stratejisini belirler.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            str: Tavsiye edilen yaklaşım stili
        """
        profile = self.profile_cache.get(user_id, {})
        communication_style = profile.get('communication_style', 'arkadaşça')
        
        # İletişim stiline göre yaklaşım belirle
        if communication_style == 'resmi':
            return 'formal'
        elif communication_style == 'flörtöz':
            return 'flirty'
        elif communication_style == 'soğuk':
            return 'respectful'
        elif communication_style in ['samimi', 'arkadaşça']:
            return 'friendly'
        elif communication_style == 'profesyonel':
            return 'professional'
        else:
            return 'friendly'
    
    def get_user_interests(self, user_id: int) -> List[str]:
        """
        Kullanıcının ilgi alanlarını döndürür.
        
        Args:
            user_id: Kullanıcı ID'si
            
        Returns:
            List[str]: İlgi alanları listesi
        """
        profile = self.profile_cache.get(user_id, {})
        interests = profile.get('interests', [])
        
        # Boş ise segment bazlı varsayılan ilgileri kullan
        if not interests:
            segment = profile.get('segment', 'genel')
            segment_info = self.segments.get(segment, {})
            # 'ilgi' yerine 'interests' kullanarak düzeltildi
            return segment_info.get('interests', ['genel'])
            
        return interests
    
    def get_personalized_message(self, user_id: int, template_type: str = 'greeting') -> str:
        """
        Kullanıcıya özel mesaj oluşturur.
        
        Args:
            user_id: Kullanıcı ID'si
            template_type: Mesaj şablonu türü
            
        Returns:
            str: Kişiselleştirilmiş mesaj
        """
        profile = self.profile_cache.get(user_id, {})
        
        # Kullanıcı adı
        name = profile.get('first_name', 'Değerli Kullanıcı')
        
        # İlgi alanı
        interests = profile.get('interests', [])
        interest = random.choice(interests) if interests else "sohbet"
        
        # Tavsiye edilen yaklaşım
        approach = self.get_recommended_approach(user_id)
        
        # Şablonları yükle
        messages = {
            'greeting': {
                'formal': f"Merhaba {name}, size nasıl yardımcı olabilirim?",
                'friendly': f"Selam {name}! Bugün nasıl gidiyor? {interest} ile ilgileniyor musun?",
                'flirty': f"Hey {name}! Seni görmek harika, bugün ne yapıyorsun? 😊",
                'professional': f"Merhaba {name}, bugün hangi konuda sohbet etmek istersin?",
                'respectful': f"Merhaba, size nasıl hitap etmemi tercih edersiniz?"
            },
            'invitation': {
                'formal': f"{name}, sizi grubumuzda görmekten memnuniyet duyarız.",
                'friendly': f"Hey {name}! Seni aramızda görmek çok güzel olur!",
                'flirty': f"{name}, seninle grubumuzda sohbet etmek harika olurdu! 💫",
                'professional': f"{name}, ilgi alanlarınıza uygun özel grubumuza davetlisiniz.",
                'respectful': f"Size özel bir grup davetimiz var. İlgilenirseniz katılabilirsiniz."
            }
        }
        
        # Şablon türü için uygun mesaj seç
        if template_type in messages:
            templates = messages[template_type]
            message = templates.get(approach, templates.get('friendly'))
            return message
            
        return f"Merhaba {name}!"