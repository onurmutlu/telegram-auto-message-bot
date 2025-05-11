/**
 * Telegram Bot Web Panel - End-to-End Tests
 * 
 * Bu test paketi, web panelinin temel işlevlerini kontrol eder:
 * 1. Ayarlar sayfası ve form işlemleri
 * 2. Mesaj ekleme ve listeleme
 * 3. Log sayfası
 * 4. Dashboard CRUD işlemleri
 * 
 * @group e2e
 */

import { test, expect, Page } from '@playwright/test';

// Test sabitleri
const TEST_API_ID = '12345678';
const TEST_API_HASH = 'ad78ef9c1b23d456a7890b12c34d56e7';
const TEST_BOT_TOKEN = '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ12345';
const TEST_MESSAGE = 'Merhaba Test';
const TEST_TIME = '13:45';

// Test sınıfı
test.describe('Telegram Bot Web Panel', () => {
  
  // Her testten önce
  test.beforeEach(async ({ page }) => {
    // Test başlangıç sayfası
    await page.goto('http://localhost:3000');
  });
  
  /**
   * Ayarlar sayfası testi
   * - Formun görüntülenmesi
   * - Formu doldurma ve kaydetme
   * - Başarı mesajının görünmesi
   */
  test('Ayarlar sayfası çalışmalı', async ({ page }) => {
    // Ayarlar sayfasına git
    await page.goto('http://localhost:3000/settings');
    
    // Başlığı kontrol et
    await expect(page.locator('h1')).toContainText('Ayarlar');
    
    // Formun görünür olduğunu kontrol et
    await expect(page.locator('form')).toBeVisible();
    
    // Form alanlarını doldur
    await page.fill('input[name="apiId"]', TEST_API_ID);
    await page.fill('input[name="apiHash"]', TEST_API_HASH);
    await page.fill('input[name="botToken"]', TEST_BOT_TOKEN);
    
    // Formu gönder
    await page.click('button:has-text("Kaydet")');
    
    // Başarı mesajını kontrol et
    const successMessage = await page.waitForSelector('.success-message, .alert-success', { 
      timeout: 5000,
      state: 'visible' 
    });
    await expect(successMessage).toBeVisible();
    await expect(successMessage).toContainText(/başar(ı|ılı)|kaydedildi/i);
    
    // Sayfayı yenile ve alanların dolu olduğunu doğrula
    await page.reload();
    await expect(page.locator('input[name="apiId"]')).toHaveValue(TEST_API_ID);
    await expect(page.locator('input[name="apiHash"]')).toHaveValue(TEST_API_HASH);
    await expect(page.locator('input[name="botToken"]')).toHaveValue(TEST_BOT_TOKEN);
  });
  
  /**
   * Mesaj ekleme testi
   * - Mesaj ekleme formunun doldurulması
   * - Başarılı ekleme mesajının görünmesi
   * - Dashboard'da mesajın listede görünmesi
   */
  test('Mesaj ekleme ve listeleme işlemi çalışmalı', async ({ page }) => {
    // Önce dashboard'a gidip mevcut mesaj sayısını kontrol et
    await page.goto('http://localhost:3000/dashboard');
    const initialMessageRows = await page.locator('table tbody tr').count();
    
    // Mesaj ekleme sayfasına git
    await page.goto('http://localhost:3000/add-message');
    
    // Başlığı kontrol et
    await expect(page.locator('h1, .page-title')).toContainText(/Mesaj|Ekle/i);
    
    // Form alanlarını doldur
    await page.fill('textarea[name="content"], input[name="content"]', TEST_MESSAGE);
    await page.fill('input[name="time"]', TEST_TIME);
    
    // Gruplar için bir selectbox varsa seç
    const groupSelect = page.locator('select[name="group_id"]');
    if (await groupSelect.isVisible()) {
      await groupSelect.selectOption({ index: 1 }); // İlk grup dışındaki bir grubu seç
    }
    
    // Ekle butonuna tıkla
    await page.click('button:has-text("Ekle")');
    
    // Başarı mesajını kontrol et
    const successMessage = await page.waitForSelector('.success-message, .alert-success', { 
      timeout: 5000,
      state: 'visible' 
    });
    await expect(successMessage).toBeVisible();
    await expect(successMessage).toContainText(/başar(ı|ılı)|eklendi/i);
    
    // Dashboard'a git ve eklenen mesajı kontrol et
    await page.goto('http://localhost:3000/dashboard');
    
    // Yeni eklenen mesajın göründüğünü doğrula
    const newMessageRows = await page.locator('table tbody tr').count();
    expect(newMessageRows).toBeGreaterThan(initialMessageRows);
    
    // Mesaj içeriğini kontrol et
    const tableRows = await page.locator('table tbody tr').all();
    let foundMessage = false;
    
    for (const row of tableRows) {
      const cellText = await row.textContent();
      if (cellText && cellText.includes(TEST_MESSAGE)) {
        foundMessage = true;
        break;
      }
    }
    
    expect(foundMessage).toBeTruthy();
  });
  
  /**
   * Log sayfası testi
   * - Logların listelenmesi
   * - En az bir log öğesinin görünür olması
   */
  test('Log sayfası çalışmalı', async ({ page }) => {
    // Log sayfasına git
    await page.goto('http://localhost:3000/logs');
    
    // Başlığı kontrol et
    await expect(page.locator('h1, .page-title')).toContainText(/Log|Loglar/i);
    
    // Logların yüklenmesini bekle
    // Not: Burada birden fazla seçici deniyoruz çünkü frontend tasarımı farklı olabilir
    await page.waitForSelector('.log-list li, ul.logs li, table.logs tbody tr', { 
      timeout: 5000,
      state: 'attached' 
    });
    
    // En az bir log öğesinin olduğunu kontrol et
    const logItems = await page.locator('.log-list li, ul.logs li, table.logs tbody tr').count();
    expect(logItems).toBeGreaterThan(0);
  });
  
  /**
   * Dashboard CRUD işlemleri testi
   * - Mesaj silme
   * - Mesaj güncelleme
   */
  test('Dashboard mesaj işlemleri çalışmalı', async ({ page }) => {
    // Önce yeni bir mesaj oluştur
    await createTestMessage(page, 'Silinecek test mesajı');
    
    // Dashboard'a git
    await page.goto('http://localhost:3000/dashboard');
    
    // Oluşturulan mesajın satırını bul
    const messageRow = await page.locator('table tbody tr')
      .filter({ hasText: 'Silinecek test mesajı' })
      .first();
    
    // Mesajın sıra numarasını al (gerekebilir)
    const rowIndex = await page.evaluate(el => {
      return Array.from(el.parentElement.children).indexOf(el);
    }, await messageRow.elementHandle());
    
    // Düzenle butonuna tıkla (eğer varsa)
    const editButton = messageRow.locator('button:has-text("Düzenle"), a:has-text("Düzenle")');
    if (await editButton.count() > 0) {
      await editButton.click();
      
      // Düzenleme formunu doldur (frontend tasarımına göre değişebilir)
      await page.fill('textarea[name="content"], input[name="content"]', 'Güncellenmiş mesaj');
      
      // Kaydet butonuna tıkla
      await page.click('button:has-text("Güncelle"), button:has-text("Kaydet")');
      
      // Başarı mesajını kontrol et
      await expect(page.locator('.success-message, .alert-success')).toBeVisible();
      
      // Dashboard'a dön ve güncellenmiş mesajı kontrol et
      await page.goto('http://localhost:3000/dashboard');
      await expect(page.locator('table tbody tr')
        .filter({ hasText: 'Güncellenmiş mesaj' })).toBeVisible();
    }
    
    // Sil butonuna tıkla
    const deleteButton = page.locator('table tbody tr')
      .filter({ hasText: 'Güncellenmiş mesaj' })
      .locator('button:has-text("Sil"), a:has-text("Sil")');
    
    if (await deleteButton.count() > 0) {
      // Silme işlemi öncesi satır sayısını al
      const beforeDeleteCount = await page.locator('table tbody tr').count();
      
      // Sil butonuna tıkla
      await deleteButton.click();
      
      // Onay diyaloğu varsa onayla
      const confirmButton = page.locator('button:has-text("Onayla"), button:has-text("Evet")');
      if (await confirmButton.count() > 0) {
        await confirmButton.click();
      }
      
      // Satırın kaybolmasını bekle
      await page.waitForTimeout(1000); // Silme işleminin tamamlanması için biraz bekle
      
      // Silme işlemi sonrası satır sayısını kontrol et
      const afterDeleteCount = await page.locator('table tbody tr').count();
      expect(afterDeleteCount).toBeLessThan(beforeDeleteCount);
    }
  });
  
});

/**
 * Test mesajı oluşturma yardımcı fonksiyonu
 */
async function createTestMessage(page: Page, content: string): Promise<void> {
  // Mesaj ekleme sayfasına git
  await page.goto('http://localhost:3000/add-message');
  
  // Form alanlarını doldur
  await page.fill('textarea[name="content"], input[name="content"]', content);
  await page.fill('input[name="time"]', '15:30');
  
  // Grup seçici varsa doldur
  const groupSelect = page.locator('select[name="group_id"]');
  if (await groupSelect.isVisible()) {
    await groupSelect.selectOption({ index: 1 });
  }
  
  // Ekle butonuna tıkla
  await page.click('button:has-text("Ekle")');
  
  // Başarı mesajının gelmesini bekle
  await page.waitForSelector('.success-message, .alert-success', { 
    timeout: 5000,
    state: 'visible' 
  });
} 