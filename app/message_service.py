from typing import List, Dict
import traceback

class MessageService:
    async def _get_active_groups(self) -> List[Dict]:
        """
        Aktif grupları veritabanından alır.
        
        Returns:
            List[Dict]: Aktif grupların listesi
        """
        try:
            groups = []
            
            # Veritabanı bağlantısını kontrol et
            if not self.db.connected:
                await self.db.connect()
                
            # 1. Yöntem: groups tablosunu kontrol et (doğru kolon isimleriyle)
            try:
                query = """
                    SELECT group_id, name, description, member_count, is_active 
                    FROM groups 
                    WHERE is_active = TRUE 
                    ORDER BY member_count DESC
                    LIMIT 100
                """
                rows = await self.db.fetchall(query)
                
                if rows and len(rows) > 0:
                    for row in rows:
                        try:
                            group_id = int(row[0])
                            groups.append({
                                'group_id': group_id,
                                'name': row[1] if len(row) > 1 else f"Grup {group_id}",
                                'description': row[2] if len(row) > 2 else "",
                                'member_count': row[3] if len(row) > 3 else 0,
                                'is_active': row[4] if len(row) > 4 else True,
                                'category': 'general'
                            })
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Grup ID çevirme hatası: {row[0]} - {str(e)}")
                            
                    if groups:
                        logger.info(f"Veritabanından {len(groups)} aktif grup başarıyla alındı")
                        return groups
            except Exception as e:
                logger.warning(f"Standart groups tablosu sorgulanırken hata: {str(e)}")
                
            # 2. Yöntem: Farklı tablo adlarıyla dene
            table_names = ['groups', 'telegram_groups', 'tg_groups']
            
            for table_name in table_names:
                try:
                    # Şema bilgisini almak için INFORMATION_SCHEMA sorgulayalım
                    schema_query = f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}'
                    """
                    columns = await self.db.fetchall(schema_query)
                    
                    if not columns:
                        continue
                        
                    # Mevcut sütunları kontrol edelim
                    column_names = [col[0] for col in columns]
                    
                    # Tablo yapısına göre uygun sorgu oluştur
                    id_column = 'group_id' if 'group_id' in column_names else ('id' if 'id' in column_names else None)
                    name_column = 'name' if 'name' in column_names else ('title' if 'title' in column_names else None)
                    
                    if id_column and name_column:
                        query = f"""
                            SELECT {id_column}, {name_column}
                            FROM {table_name}
                            WHERE is_active = TRUE
                            LIMIT 100
                        """
                        
                        rows = await self.db.fetchall(query)
                        
                        formatted_groups = []
                        for row in rows:
                            try:
                                group_id = int(row[0])
                                formatted_groups.append({
                                    'group_id': group_id,
                                    'name': row[1] if row[1] else f"Grup {group_id}",
                                    'category': 'general'
                                })
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Grup ID çevirme hatası: {row[0]} - {str(e)}")
                                
                        if formatted_groups:
                            logger.info(f"{table_name} tablosundan {len(formatted_groups)} aktif grup alındı")
                            return formatted_groups
                except Exception as e:
                    logger.warning(f"{table_name} tablosu sorgulanırken hata: {str(e)}")
            
            # 4. Yöntem: Sabit gruplara geri dön (son çare)
            if not groups:
                logger.warning("Veritabanından grup alınamadı! Varsayılan test gruplarını kullanıyorum.")
                # Varsayılan test grupları ekle
                fallback_groups = []
                
                # Config dosyasından default grup ID'leri varsa onları kullan
                if hasattr(self.config, 'get_setting'):
                    default_group_ids = self.config.get_setting('DEFAULT_GROUP_IDS', '')
                    if default_group_ids:
                        for group_id_str in default_group_ids.split(','):
                            try:
                                group_id = int(group_id_str.strip())
                                fallback_groups.append({
                                    'group_id': group_id,
                                    'name': f"Default Grup {group_id}",
                                    'category': 'general'
                                })
                            except ValueError:
                                pass
                
                # Hiç grup bulunamazsa
                if not fallback_groups:
                    logger.warning("Hiç varsayılan grup bulunamadı. Mesaj gönderilemeyecek!")
                    
                return fallback_groups
            
            return []
        except Exception as e:
            logger.error(f"Aktif gruplar alınırken hata: {str(e)}")
            logger.debug(traceback.format_exc())
            return [] 