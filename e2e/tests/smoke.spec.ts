/**
 * Telegram Bot Web Panel - Smoke Tests
 * 
 * Bu dosya, web panelinin E2E smoke testlerini içerir:
 * - Ayarları doldurma ve kaydetme
 * - Mesaj ekleme
 * - Log sayfasını kontrol etme
 * 
 * @group smoke
 */

import { test, expect } from '@playwright/test';

// Test sabitleri
const TEST_API_ID = '12345678';
const TEST_API_HASH = 'a1b2c3d4e5f6g7h8i9j0';
const TEST_BOT_TOKEN = '1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const TEST_MESSAGE = 'Merhaba Test';
const TEST_TIME = '23:59';

test.describe('Telegram Bot Web Panel Smoke Tests', () => {
  // Her testten önce
  test.beforeEach(async ({ page }) => {
    // Ana sayfaya git
    await page.goto('http://localhost:3000');
  });

  test('Ayarlar sayfası çalışmalı ve form kaydetmeli', async ({ page }) => {
    // Ayarlar sayfasına git
    await page.click('text=Ayarlar');
    
    // Sayfa başlığını kontrol et
    await expect(page.locator('h1')).toContainText('Ayarlar');
    
    // Formu doldur
    await page.fill('input[name="apiId"]', TEST_API_ID);
    await page.fill('input[name="apiHash"]', TEST_API_HASH);
    await page.fill('input[name="botToken"]', TEST_BOT_TOKEN);
    
    // Kaydet butonuna tıkla
    await page.click('button:has-text("Kaydet")');
    
    // Başarı mesajını bekle ve doğrula
    const successMessage = await page.waitForSelector('.success-message', { timeout: 5000 });
    await expect(successMessage).toBeVisible();
    await expect(successMessage).toContainText('Ayarlar başarıyla kaydedildi');
  });

  test('Mesaj ekleme işlemi çalışmalı', async ({ page }) => {
    // Mesaj ekleme sayfasına git
    await page.click('text=Mesaj Ekle');
    
    // Sayfa başlığını kontrol et
    await expect(page.locator('h1')).toContainText('Mesaj Ekle');
    
    // Formu doldur
    await page.fill('textarea[name="content"]', TEST_MESSAGE);
    await page.fill('input[name="time"]', TEST_TIME);
    
    // Mesaj sayısını kontrol et (ekleme öncesi)
    const initialMessageCount = await page.locator('.message-list li').count();
    
    // Ekle butonuna tıkla
    await page.click('button:has-text("Ekle")');
    
    // Başarı mesajını bekle ve doğrula
    const successMessage = await page.waitForSelector('.success-message', { timeout: 5000 });
    await expect(successMessage).toBeVisible();
    await expect(successMessage).toContainText('Mesaj başarıyla eklendi');
    
    // Mesaj listesini yenile ve yeni mesaj sayısını kontrol et
    await page.click('text=Mesajlar');
    const newMessageCount = await page.locator('.message-list li').count();
    expect(newMessageCount).toBeGreaterThan(initialMessageCount);
    
    // Eklenen mesajın içeriğini kontrol et
    const messages = await page.locator('.message-list li').allTextContents();
    const hasMessage = messages.some(msg => msg.includes(TEST_MESSAGE));
    expect(hasMessage).toBeTruthy();
  });
  
  test('Log sayfası en az bir log göstermeli', async ({ page }) => {
    // Log sayfasına git
    await page.click('text=Loglar');
    
    // Sayfa başlığını kontrol et
    await expect(page.locator('h1')).toContainText('Loglar');
    
    // Log öğelerinin yüklenmesini bekle (en az bir tane olmalı)
    await page.waitForSelector('.log-list li', { timeout: 5000 });
    
    // En az bir log gösterildiğini doğrula
    const logCount = await page.locator('.log-list li').count();
    expect(logCount).toBeGreaterThan(0);
  });
}); 