/**
 * Telegram Bot Web Panel - Tam E2E Testi
 * 
 * Bu test, web panelin tüm ana işlevlerini kapsar:
 * 1. Ayarlar sayfasında form doldurma ve kaydetme
 * 2. Yeni mesaj ekleme
 * 3. Dashboard'da mesaj listeleme, güncelleme ve silme
 * 4. Log kayıtlarını kontrol etme
 * 
 * @group e2e
 * @group full-app
 */

import { test, expect, Page } from '@playwright/test';

// Test sabitleri
const TEST_API_ID = '12345678';
const TEST_API_HASH = 'ad78ef9c1b23d456a7890b12c34d56e7';
const TEST_BOT_TOKEN = '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ12345';
const TEST_MESSAGE = 'Bu bir test mesajıdır - ' + new Date().toISOString();
const TEST_TIME = '15:30';
const UPDATED_MESSAGE = 'Güncellenmiş test mesajı - ' + new Date().toISOString();

/**
 * Başarı mesajını kontrol etmek için yardımcı fonksiyon
 */
async function expectSuccessMessage(page: Page, timeout = 5000): Promise<void> {
  // Başarı mesajı için birden fazla olası CSS seçici dene
  const successSelector = [
    '.success-message', 
    '.alert-success', 
    '.toast-success',
    '[role="alert"]:has-text("başarı")',
    '[role="alert"]:has-text("success")'
  ].join(', ');
  
  const successMessage = await page.waitForSelector(successSelector, { timeout });
  await expect(successMessage).toBeVisible();
}

/**
 * Ana test paketi
 */
test.describe('Telegram Bot Web Panel E2E', () => {
  // Test öncesi ayarlar
  test.beforeEach(async ({ page }) => {
    // Test her zaman ana sayfada başlar
    await page.goto('http://localhost:3000');
    console.log('Ana sayfaya gidildi');
  });
  
  /**
   * Tam E2E testi - tüm işlevleri tek bir akışta test eder
   */
  test('Tam uygulama akışı', async ({ page }) => {
    // ----- 1. AYARLAR SAYFASI -----
    console.log('Ayarlar sayfası testi başlıyor...');
    
    // Ayarlar sayfasına git
    await page.goto('http://localhost:3000/settings');
    
    // Sayfanın yüklendiğini doğrula
    await expect(page.locator('h1, .page-title')).toContainText(/Ayarlar|Settings/i);
    
    // Form görünür olmalı
    await expect(page.locator('form')).toBeVisible();
    
    // Form alanlarını doldur
    await page.fill('input[name="apiId"]', TEST_API_ID);
    await page.fill('input[name="apiHash"]', TEST_API_HASH);
    await page.fill('input[name="botToken"]', TEST_BOT_TOKEN);
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/01-settings-form.png' });
    
    // Kaydet butonuna tıkla
    await page.click('button:has-text("Kaydet")');
    
    // Başarı mesajını bekle
    await expectSuccessMessage(page);
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/02-settings-saved.png' });
    
    console.log('✓ Ayarlar başarıyla kaydedildi');

    // ----- 2. MESAJ EKLEME SAYFASI -----
    console.log('Mesaj ekleme testi başlıyor...');
    
    // Mesaj ekleme sayfasına git
    await page.goto('http://localhost:3000/add-message');
    
    // Sayfanın yüklendiğini doğrula
    await expect(page.locator('h1, .page-title')).toContainText(/Mesaj|Ekle|Message|Add/i);
    
    // Form alanlarını doldur
    if (await page.locator('textarea[name="content"]').count() > 0) {
      await page.fill('textarea[name="content"]', TEST_MESSAGE);
    } else {
      await page.fill('input[name="content"]', TEST_MESSAGE);
    }
    
    await page.fill('input[name="time"]', TEST_TIME);
    
    // Grup seçimi varsa ilk öğeyi seç
    const groupSelect = page.locator('select[name="group_id"]');
    if (await groupSelect.count() > 0) {
      // İlk seçeneği seç (indeks 1, çünkü indeks 0 genellikle "Seçiniz" olabilir)
      await groupSelect.selectOption({ index: 1 });
    }
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/03-add-message-form.png' });
    
    // Ekle butonuna tıkla
    await page.click('button:has-text("Ekle")');
    
    // Başarı mesajını bekle
    await expectSuccessMessage(page);
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/04-message-added.png' });
    
    console.log('✓ Mesaj başarıyla eklendi');
    
    // ----- 3. DASHBOARD SAYFASI -----
    console.log('Dashboard testi başlıyor...');
    
    // Dashboard sayfasına git
    await page.goto('http://localhost:3000/dashboard');
    
    // Sayfanın yüklendiğini doğrula
    await expect(page.locator('h1, .page-title')).toContainText(/Dashboard|Mesajlar|Messages/i);
    
    // Tablo veya liste görünür olmalı
    const listElements = [
      'table tbody tr', 
      '.message-list li',
      '.messages-container .message-item'
    ];
    
    // Mesaj listesinin görünmesini bekle
    const messageListSelector = listElements.join(', ');
    await page.waitForSelector(messageListSelector, { timeout: 5000 });
    
    // Eklediğimiz mesajı bul
    // Mesaj içeriğine göre satırı bulmaya çalış
    const messageRowLocator = page.locator([
      `table tbody tr:has-text("${TEST_MESSAGE}")`,
      `.message-list li:has-text("${TEST_MESSAGE}")`,
      `.message-item:has-text("${TEST_MESSAGE}")`
    ].join(', '));
    
    // Mesajın görünür olduğunu doğrula
    await expect(messageRowLocator).toBeVisible();
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/05-dashboard-with-message.png' });
    
    console.log('✓ Dashboard mesaj listesi doğrulandı');
    
    // ----- 4. MESAJ GÜNCELLEME -----
    console.log('Mesaj güncelleme testi başlıyor...');
    
    // Düzenle/Güncelle butonunu bul ve tıkla
    const editButtonSelector = [
      `table tbody tr:has-text("${TEST_MESSAGE}") button:has-text("Düzenle"), table tbody tr:has-text("${TEST_MESSAGE}") a:has-text("Düzenle")`,
      `.message-list li:has-text("${TEST_MESSAGE}") button:has-text("Düzenle"), .message-list li:has-text("${TEST_MESSAGE}") a:has-text("Düzenle")`,
      `.message-item:has-text("${TEST_MESSAGE}") button:has-text("Düzenle"), .message-item:has-text("${TEST_MESSAGE}") a:has-text("Düzenle")`,
      `table tbody tr:has-text("${TEST_MESSAGE}") button:has-text("Güncelle"), table tbody tr:has-text("${TEST_MESSAGE}") a:has-text("Güncelle")`,
      `.message-list li:has-text("${TEST_MESSAGE}") button:has-text("Güncelle"), .message-list li:has-text("${TEST_MESSAGE}") a:has-text("Güncelle")`,
      `.message-item:has-text("${TEST_MESSAGE}") button:has-text("Güncelle"), .message-item:has-text("${TEST_MESSAGE}") a:has-text("Güncelle")`
    ].join(', ');
    
    await page.click(editButtonSelector);
    
    // Düzenleme formunun görünmesini bekle
    await page.waitForSelector('form', { timeout: 5000 });
    
    // Mesaj içeriğini güncelle
    if (await page.locator('textarea[name="content"]').count() > 0) {
      await page.fill('textarea[name="content"]', UPDATED_MESSAGE);
    } else {
      await page.fill('input[name="content"]', UPDATED_MESSAGE);
    }
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/06-edit-message-form.png' });
    
    // Kaydet/Güncelle butonuna tıkla
    const updateButtonSelector = [
      'button:has-text("Güncelle")',
      'button:has-text("Kaydet")',
      'button:has-text("Update")',
      'button:has-text("Save")'
    ].join(', ');
    
    await page.click(updateButtonSelector);
    
    // Başarı mesajını bekle
    await expectSuccessMessage(page);
    
    // Dashboard'a geri dön
    await page.goto('http://localhost:3000/dashboard');
    
    // Güncellenen mesajın görünmesini bekle
    const updatedMessageRowLocator = page.locator([
      `table tbody tr:has-text("${UPDATED_MESSAGE}")`,
      `.message-list li:has-text("${UPDATED_MESSAGE}")`,
      `.message-item:has-text("${UPDATED_MESSAGE}")`
    ].join(', '));
    
    // Güncellenmiş mesajın görünür olduğunu doğrula
    await expect(updatedMessageRowLocator).toBeVisible();
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/07-dashboard-with-updated-message.png' });
    
    console.log('✓ Mesaj başarıyla güncellendi');
    
    // ----- 5. MESAJ SİLME -----
    console.log('Mesaj silme testi başlıyor...');
    
    // İlk olarak mesaj sayısını kontrol et
    const messageCountBefore = await page.locator([
      'table tbody tr',
      '.message-list li',
      '.message-item'
    ].join(', ')).count();
    
    // Sil butonunu bul ve tıkla
    const deleteButtonSelector = [
      `table tbody tr:has-text("${UPDATED_MESSAGE}") button:has-text("Sil"), table tbody tr:has-text("${UPDATED_MESSAGE}") a:has-text("Sil")`,
      `.message-list li:has-text("${UPDATED_MESSAGE}") button:has-text("Sil"), .message-list li:has-text("${UPDATED_MESSAGE}") a:has-text("Sil")`,
      `.message-item:has-text("${UPDATED_MESSAGE}") button:has-text("Sil"), .message-item:has-text("${UPDATED_MESSAGE}") a:has-text("Sil")`,
      `table tbody tr:has-text("${UPDATED_MESSAGE}") button:has-text("Delete"), table tbody tr:has-text("${UPDATED_MESSAGE}") a:has-text("Delete")`,
      `.message-list li:has-text("${UPDATED_MESSAGE}") button:has-text("Delete"), .message-list li:has-text("${UPDATED_MESSAGE}") a:has-text("Delete")`,
      `.message-item:has-text("${UPDATED_MESSAGE}") button:has-text("Delete"), .message-item:has-text("${UPDATED_MESSAGE}") a:has-text("Delete")`
    ].join(', ');
    
    await page.click(deleteButtonSelector);
    
    // Onay diyaloğu varsa "evet" veya "onayla" butonuna tıkla
    const confirmDialog = page.locator([
      'div.modal, div.dialog, div.confirm-dialog',
      '[role="dialog"]',
      '.confirmation-popup'
    ].join(', '));
    
    if (await confirmDialog.count() > 0) {
      const confirmButtonSelector = [
        'button:has-text("Evet")',
        'button:has-text("Onayla")',
        'button:has-text("Tamam")',
        'button:has-text("Yes")',
        'button:has-text("Confirm")',
        'button:has-text("OK")'
      ].join(', ');
      
      await page.click(confirmButtonSelector);
    }
    
    // Başarı mesajını bekle
    await expectSuccessMessage(page);
    
    // Silinen mesajın artık görünmediğini doğrula (yok olmasını bekle)
    await expect(updatedMessageRowLocator).toHaveCount(0);
    
    // Alternatif olarak mesaj sayısının azaldığını kontrol et
    await page.waitForTimeout(1000); // Silme işleminin tamamlanması için kısa bir bekleme
    const messageCountAfter = await page.locator([
      'table tbody tr',
      '.message-list li',
      '.message-item'
    ].join(', ')).count();
    
    // Mesaj sayısı azalmış olmalı
    expect(messageCountAfter).toBeLessThan(messageCountBefore);
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/08-dashboard-after-delete.png' });
    
    console.log('✓ Mesaj başarıyla silindi');
    
    // ----- 6. LOG SAYFASI -----
    console.log('Log sayfası testi başlıyor...');
    
    // Log sayfasına git
    await page.goto('http://localhost:3000/logs');
    
    // Sayfanın yüklendiğini doğrula
    await expect(page.locator('h1, .page-title')).toContainText(/Log|Loglar|Logs/i);
    
    // Log öğelerinin yüklenmesini bekle
    const logItemSelector = [
      '.log-list li',
      'ul.logs li',
      'table.logs tbody tr',
      '.log-entry',
      '.log-item'
    ].join(', ');
    
    await page.waitForSelector(logItemSelector, { timeout: 5000 });
    
    // En az bir log öğesi olmalı
    const logCount = await page.locator(logItemSelector).count();
    expect(logCount).toBeGreaterThan(0);
    
    // Tüm log öğelerinin metinlerini al
    const logTexts = await page.locator(logItemSelector).allTextContents();
    const logContent = logTexts.join(' ').toLowerCase();
    
    // İşlemlerin loglanmış olduğunu doğrula (işlem türlerine göre uygun anahtar kelimeleri ara)
    const hasSettingsLog = logContent.includes('ayarlar') || logContent.includes('settings') || logContent.includes('kaydet');
    const hasAddLog = logContent.includes('ekle') || logContent.includes('add') || logContent.includes('create') || logContent.includes('message');
    const hasUpdateLog = logContent.includes('güncelle') || logContent.includes('update') || logContent.includes('edit');
    const hasDeleteLog = logContent.includes('sil') || logContent.includes('delete') || logContent.includes('remove');
    
    // En az bir işlem türü loglanmış olmalı
    expect(hasSettingsLog || hasAddLog || hasUpdateLog || hasDeleteLog).toBeTruthy();
    
    // Her işlem türü için log kayıtlarının varlığını kontrol et ve rapor et
    if (hasSettingsLog) console.log('✓ Ayarlar log kaydı bulundu');
    if (hasAddLog) console.log('✓ Mesaj ekleme log kaydı bulundu');
    if (hasUpdateLog) console.log('✓ Mesaj güncelleme log kaydı bulundu');
    if (hasDeleteLog) console.log('✓ Mesaj silme log kaydı bulundu');
    
    // Ekran görüntüsü al
    await page.screenshot({ path: './test-results/09-logs-page.png' });
    
    console.log('✓ Log sayfası başarıyla test edildi');
    
    // ----- TEST TAMAMLANDI -----
    console.log('\n✓ Tüm E2E testi başarıyla tamamlandı!');
  });
}); 