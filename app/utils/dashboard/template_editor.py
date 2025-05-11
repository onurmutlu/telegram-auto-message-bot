"""
Şablon düzenleyici modülü.
Mesaj, davet ve yanıt şablonlarını düzenlemek için arayüz sağlar.
"""
import os
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def template_editor(dashboard, template_type):
    """
    Şablonları düzenlemek için ana fonksiyon.
    
    Args:
        dashboard: Dashboard nesnesi
        template_type: Şablon türü ("messages", "invites", "responses")
    """
    dashboard.clear_screen()
    
    title_map = {
        "messages": "MESAJ ŞABLONLARI",
        "invites": "DAVET ŞABLONLARI",
        "responses": "YANIT ŞABLONLARI"
    }
    
    file_map = {
        "messages": os.getenv("MESSAGES_FILE", "data/messages.json"),
        "invites": os.getenv("INVITES_FILE", "data/invites.json"),
        "responses": os.getenv("RESPONSES_FILE", "data/responses.json")
    }
    
    title = title_map.get(template_type, "ŞABLON EDİTÖRÜ")
    file_path = file_map.get(template_type)
    
    dashboard.console.print(Panel.fit(
        f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan"
    ))
    
    # Dosya kontrolü
    if not os.path.exists(file_path):
        dashboard.console.print(f"[yellow]Şablon dosyası bulunamadı: {file_path}[/yellow]")
        dashboard.console.print("[yellow]Boş bir şablon oluşturuluyor...[/yellow]")
        
        if template_type == "messages":
            data = ["Örnek mesaj 1", "Örnek mesaj 2"]
        elif template_type == "invites":
            data = {
                "first_invite": ["Örnek davet 1", "Örnek davet 2"],
                "redirect": ["Örnek yönlendirme 1"]
            }
        else:  # responses
            data = {
                "flirty": ["Örnek yanıt 1", "Örnek yanıt 2"],
                "casual": ["Örnek günlük yanıt"]
            }
            
        save_templates(file_path, data)
    
    # Şablon verilerini yükle
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        dashboard.console.print(f"[red]Şablon dosyası okunamadı: {e}[/red]")
        Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
        return
    
    # Şablon türüne göre düzenleme fonksiyonunu çağır
    if template_type == "messages":
        edit_simple_templates(dashboard, file_path, data, template_type)
    else:  # invites, responses
        edit_categorized_templates(dashboard, file_path, data, template_type)

def edit_simple_templates(dashboard, file_path, templates, template_type):
    """Basit liste şeklindeki şablonları düzenler"""
    while True:
        dashboard.clear_screen()
        
        dashboard.console.print(Panel.fit(
            f"[bold cyan]MESAJ ŞABLONLARI DÜZENLEME[/bold cyan]",
            border_style="cyan"
        ))
        
        # Şablon listesini göster
        dashboard.console.print(f"[bold]Toplam {len(templates)} şablon:[/bold]")
        for i, template in enumerate(templates):
            # Uzun şablonları kısalt
            display = template if len(template) < 60 else template[:57] + "..."
            dashboard.console.print(f"{i+1}. [cyan]{display}[/cyan]")
        
        # Seçenekler
        dashboard.console.print("\n[bold]İşlemler:[/bold]")
        dashboard.console.print("1. Şablon ekle")
        dashboard.console.print("2. Şablonu düzenle")
        dashboard.console.print("3. Şablon sil")
        dashboard.console.print("4. Şablonları kaydet")
        dashboard.console.print("5. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice == "1":
            new_template = Prompt.ask("Yeni şablon metni")
            templates.append(new_template)
            save_templates(file_path, templates)
            dashboard.console.print(f"[green]✅ Yeni şablon eklendi[/green]")
            
        elif choice == "2" and templates:
            edit_idx = IntPrompt.ask(
                "Düzenlemek istediğiniz şablonun numarası", 
                min_value=1,
                max_value=len(templates)
            )
            
            current = templates[edit_idx - 1]
            dashboard.console.print(f"Mevcut şablon: [cyan]{current}[/cyan]")
            
            new_value = Prompt.ask("Yeni şablon metni", default=current)
            templates[edit_idx - 1] = new_value
            save_templates(file_path, templates)
            dashboard.console.print(f"[green]✅ Şablon güncellendi[/green]")
            
        elif choice == "3" and templates:
            delete_idx = IntPrompt.ask(
                "Silmek istediğiniz şablonun numarası", 
                min_value=1,
                max_value=len(templates)
            )
            
            deleted = templates.pop(delete_idx - 1)
            save_templates(file_path, templates)
            dashboard.console.print(f"[green]✅ Şablon silindi: {deleted}[/green]")
            
        elif choice == "4":
            save_templates(file_path, templates)
            dashboard.console.print(f"[green]✅ Şablonlar kaydedildi[/green]")
            
        elif choice == "5":
            break
            
        # Her işlemden sonra kısa bekle
        Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")

def edit_categorized_templates(dashboard, file_path, categories, template_type):
    """Kategorili şablonları düzenler (davet ve yanıt şablonları)"""
    while True:
        dashboard.clear_screen()
        
        title = "DAVET ŞABLONLARI" if template_type == "invites" else "YANIT ŞABLONLARI"
        dashboard.console.print(Panel.fit(
            f"[bold cyan]{title} DÜZENLEME[/bold cyan]",
            border_style="cyan"
        ))
        
        # Kategorileri göster
        dashboard.console.print(f"[bold]Toplam {len(categories)} kategori:[/bold]")
        for i, (category, templates) in enumerate(categories.items()):
            dashboard.console.print(f"{i+1}. [cyan]{category}[/cyan] ({len(templates)} şablon)")
        
        # Seçenekler
        dashboard.console.print("\n[bold]İşlemler:[/bold]")
        dashboard.console.print("1. Kategori seç ve düzenle")
        dashboard.console.print("2. Yeni kategori ekle")
        dashboard.console.print("3. Kategori sil")
        dashboard.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1" and categories:
            # Kategori seç
            category_names = list(categories.keys())
            for i, name in enumerate(category_names):
                dashboard.console.print(f"{i+1}. [cyan]{name}[/cyan]")
                
            cat_idx = IntPrompt.ask(
                "Düzenlemek istediğiniz kategorinin numarası",
                min_value=1,
                max_value=len(category_names)
            )
            
            selected_category = category_names[cat_idx - 1]
            templates = categories[selected_category]
            
            # Seçilen kategorideki şablonları düzenle
            while True:
                dashboard.clear_screen()
                dashboard.console.print(Panel.fit(
                    f"[bold cyan]{selected_category.upper()} KATEGORİSİ[/bold cyan]",
                    border_style="cyan"
                ))
                
                # Şablonları göster
                dashboard.console.print(f"[bold]Toplam {len(templates)} şablon:[/bold]")
                for i, template in enumerate(templates):
                    # Uzun şablonları kısalt
                    display = template if len(template) < 60 else template[:57] + "..."
                    dashboard.console.print(f"{i+1}. [cyan]{display}[/cyan]")
                
                # Alt menü
                dashboard.console.print("\n[bold]İşlemler:[/bold]")
                dashboard.console.print("1. Şablon ekle")
                dashboard.console.print("2. Şablonu düzenle")
                dashboard.console.print("3. Şablon sil")
                dashboard.console.print("4. Geri")
                
                sub_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
                
                if sub_choice == "1":
                    new_template = Prompt.ask("Yeni şablon metni")
                    templates.append(new_template)
                    save_templates(file_path, categories)
                    dashboard.console.print(f"[green]✅ Yeni şablon eklendi[/green]")
                    
                elif sub_choice == "2" and templates:
                    edit_idx = IntPrompt.ask(
                        "Düzenlemek istediğiniz şablonun numarası", 
                        min_value=1,
                        max_value=len(templates)
                    )
                    
                    current = templates[edit_idx - 1]
                    dashboard.console.print(f"Mevcut şablon: [cyan]{current}[/cyan]")
                    
                    new_value = Prompt.ask("Yeni şablon metni", default=current)
                    templates[edit_idx - 1] = new_value
                    save_templates(file_path, categories)
                    dashboard.console.print(f"[green]✅ Şablon güncellendi[/green]")
                    
                elif sub_choice == "3" and templates:
                    delete_idx = IntPrompt.ask(
                        "Silmek istediğiniz şablonun numarası", 
                        min_value=1,
                        max_value=len(templates)
                    )
                    
                    deleted = templates.pop(delete_idx - 1)
                    save_templates(file_path, categories)
                    dashboard.console.print(f"[green]✅ Şablon silindi: {deleted}[/green]")
                    
                elif sub_choice == "4":
                    break
                    
                # Her işlemden sonra kısa bekle
                Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
            
        elif choice == "2":
            new_category = Prompt.ask("Yeni kategori adı")
            if new_category and new_category not in categories:
                categories[new_category] = []
                save_templates(file_path, categories)
                dashboard.console.print(f"[green]✅ Yeni kategori eklendi: {new_category}[/green]")
            else:
                dashboard.console.print("[yellow]Kategori adı boş olamaz veya mevcut kategorilerle aynı olamaz.[/yellow]")
                
        elif choice == "3" and categories:
            # Kategori listesi
            category_names = list(categories.keys())
            for i, name in enumerate(category_names):
                dashboard.console.print(f"{i+1}. [cyan]{name}[/cyan]")
                
            delete_idx = IntPrompt.ask(
                "Silmek istediğiniz kategorinin numarası",
                min_value=1,
                max_value=len(category_names)
            )
            
            deleted = category_names[delete_idx - 1]
            confirm = Confirm.ask(f"[yellow]{deleted}[/yellow] kategorisini ve içindeki tüm şablonları silmek istediğinize emin misiniz?")
            
            if confirm:
                del categories[deleted]
                save_templates(file_path, categories)
                dashboard.console.print(f"[green]✅ Kategori silindi: {deleted}[/green]")
                
        elif choice == "4":
            break
            
        # Her işlemden sonra kısa bekle
        Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")

def save_templates(file_path, data):
    """Şablonları dosyaya kaydeder"""
    try:
        # Dizin yapısını kontrol et
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Şablonlar kaydedilemedi: {e}")
        return False