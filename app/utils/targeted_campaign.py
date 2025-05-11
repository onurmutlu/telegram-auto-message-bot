"""
# ============================================================================ #
# Dosya: targeted_campaign.py
# Yol: /Users/siyahkare/code/telegram-bot/app/utils/targeted_campaign.py
# İşlev: Demografik verilere göre hedefli pazarlama kampanyaları oluşturma.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import json
import logging
import random
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TargetedCampaign:
    """
    Demografik verilere göre hedefli pazarlama kampanyaları oluşturma sınıfı.
    """
    
    def __init__(self, data_mining_service, invite_service=None):
        """
        Başlatıcı.
        
        Args:
            data_mining_service: DataMiningService referansı
            invite_service: Kampanyaları göndermek için InviteService (opsiyonel)
        """
        self.data_mining = data_mining_service
        self.invite_service = invite_service
        
        # Segment-kampanya eşleştirmesi
        self.segment_to_campaign_map = {
            "active": "vip",         # Aktif kullanıcılar VIP kampanyalarını alabilir
            "new": "new_products",   # Yeni kullanıcılar yeni ürün tanıtımlarını alabilir
            "dormant": "flash_sale", # İnaktif kullanıcılar acil fırsatlarla geri çekilebilir
            "premium": "membership", # Premium kullanıcılar üyelik tekliflerini alabilir
            "language": "general"    # Dil bazlı segmentler genel kampanyaları alabilir
        }
        
        # Kampanya şablonları yükleme
        try:
            with open('data/campaigns.json', 'r', encoding='utf-8') as f:
                campaign_data = json.load(f)
                self.available_campaigns = campaign_data
                
                # Bu eşleştirmeyi kullanarak segment-kampanya ilişkisi kur
                self.segment_templates = {}
                for segment, campaign_type in self.segment_to_campaign_map.items():
                    if campaign_type in campaign_data:
                        self.segment_templates[segment] = campaign_data[campaign_type]
        except Exception as e:
            logger.error(f"Kampanya şablonları yüklenirken hata: {str(e)}")
            # Varsayılan şablonlar
            self.segment_templates = {
                "active": ["Aktif kullanıcımız olarak size özel: {product}"],
                "new": ["Hoş geldiniz! Size özel: {product}"],
                "dormant": ["Sizi özledik! Geri dönün ve {product} fırsatını kaçırmayın!"]
            }
            
        # Ürün/Hizmet örnekleri
        self.products = [
            "Premium Üyelik",
            "VIP Grup Erişimi",
            "Özel İçerik Paketi",
            "Reklamsız Deneyim",
            "1 Aylık Ücretsiz Deneme"
        ]
        
    def create_campaign(self, target_segment, campaign_name, product=None):
        """
        Hedef segmente göre kampanya oluşturur.
        
        Args:
            target_segment: Hedef segment adı
            campaign_name: Kampanya adı
            product: Ürün adı (None ise rastgele seçilir)
            
        Returns:
            Dict: Kampanya bilgileri
        """
        # Ürün belirtilmemişse rastgele seç
        if not product:
            product = random.choice(self.products)
            
        # Şablon seç
        template = None
        if target_segment in self.segment_templates:
            template = random.choice(self.segment_templates[target_segment])
        else:
            # Varsayılan şablon
            template = "Özel kampanyamız: {product}"
            
        return {
            "name": campaign_name,
            "segment": target_segment,
            "product": product,
            "template": template,
            "created_at": datetime.now().isoformat(),
            "status": "created"
        }
        
    def personalize_message(self, campaign, user_data):
        """
        Kampanya mesajını kullanıcıya göre kişiselleştirir.
        
        Args:
            campaign: Kampanya bilgileri
            user_data: Kullanıcı verileri
            
        Returns:
            str: Kişiselleştirilmiş mesaj
        """
        # Kullanıcı adını al
        name = user_data.get("first_name")
        if not name:
            name = "Değerli Üyemiz"
        
        # Kampanya kategorisine göre şablon seç
        category = campaign.get("segment", "general")
        if category in self.segment_templates:
            templates = self.segment_templates[category]
        else:
            templates = self.available_campaigns.get("general", ["Özel teklif: {product}"])
        
        # Şablonu rastgele seç
        template = random.choice(templates)
            
        # Mesajı formatla
        try:
            message = template.format(
                name=name,
                product=campaign["product"]
            )
        except KeyError:
            # Format hatası durumunda basit bir mesaj dön
            message = f"Özel teklif: {campaign['product']}"
        
        return message
        
    async def send_campaign(self, campaign, batch_size=20):
        """
        Kampanyayı hedef segmentteki kullanıcılara gönderir.
        
        Args:
            campaign: Kampanya bilgileri
            batch_size: Bir seferde gönderilecek maksimum ileti sayısı
            
        Returns:
            Dict: Gönderim sonuçları
        """
        if not self.invite_service:
            return {"error": "No invite service available"}
            
        results = {
            "total_targeted": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0
        }
        
        try:
            # Hedef segmentteki kullanıcıları al
            target_users = await self.data_mining.get_user_segment(campaign["segment"])
            results["total_targeted"] = len(target_users)
            
            # Kullanıcı batch'i oluştur (maksimum batch_size kadar)
            user_batch = target_users[:batch_size]
            
            # Her kullanıcıya kampanya gönder
            for user_id in user_batch:
                try:
                    # Kullanıcı bilgilerini al
                    user_data = await self.data_mining._run_async_db_method(
                        self.data_mining.db.get_user_by_id, 
                        user_id
                    )
                    
                    if not user_data:
                        results["skipped"] += 1
                        continue
                        
                    # Mesajı kişiselleştir
                    message = self.personalize_message(campaign, user_data)
                    
                    # Kullanıcıya gönder (InviteService'in DM gönderme metodunu kullan)
                    success = await self.invite_service.send_dm_to_user(user_id, message)
                    
                    if success:
                        results["sent"] += 1
                    else:
                        results["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"Kullanıcıya kampanya gönderme hatası ({user_id}): {str(e)}")
                    results["failed"] += 1
                    
            return results
            
        except Exception as e:
            logger.error(f"Kampanya gönderme hatası: {str(e)}")
            return {"error": str(e)}
        
    def save_campaign(self, campaign):
        """
        Kampanyayı JSON dosyasına kaydeder.
        
        Args:
            campaign: Kampanya bilgileri
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Mevcut kampanyaları yükle
            campaigns = []
            try:
                with open('data/user_campaigns.json', 'r', encoding='utf-8') as f:
                    campaigns = json.load(f)
            except FileNotFoundError:
                campaigns = []
            
            # Kampanyaya ID ekle
            if "id" not in campaign:
                campaign["id"] = len(campaigns) + 1
                
            # datetime nesnelerini string'e dönüştür
            if "created_at" in campaign and isinstance(campaign["created_at"], datetime):
                campaign["created_at"] = campaign["created_at"].isoformat()
                
            # Kampanyayı ekle
            campaigns.append(campaign)
            
            # Dosyaya kaydet
            with open('data/user_campaigns.json', 'w', encoding='utf-8') as f:
                json.dump(campaigns, f, indent=2, ensure_ascii=False)
                
            return True
            
        except Exception as e:
            logger.error(f"Kampanya kaydetme hatası: {str(e)}")
            return False