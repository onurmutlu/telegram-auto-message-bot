import { defineConfig, devices } from '@playwright/test';
import path from 'path';

/**
 * Telegram Bot Web Panel - Playwright Test Konfigürasyonu
 * 
 * Bu dosya Playwright E2E testlerinin yapılandırmasını içerir.
 * 
 * API Dökümantasyonu:
 * https://playwright.dev/docs/api/class-testconfig
 */

export default defineConfig({
  // Test dosyaları
  testDir: './tests',
  
  // Her testin maksimum çalışma süresi
  timeout: 30000,
  
  // Aynı anda tüm testleri çalıştır
  fullyParallel: true,
  
  // CI modunda sadece yalnız testleri yürütmeyi engelle
  forbidOnly: !!process.env.CI,
  
  // CI modunda daha fazla yeniden deneme yap
  retries: process.env.CI ? 2 : 0,
  
  // CI modunda daha az worker kullan
  workers: process.env.CI ? 1 : undefined,
  
  // Test raporu
  reporter: [
    ['html', { open: 'never' }],
    ['list']
  ],
  
  // Ortak test kullanımı
  use: {
    // Temel URL
    baseURL: 'http://localhost:3000',
    
    // Eser izleme yalnızca ilk yeniden denemede
    trace: 'on-first-retry',
    
    // Ekran görüntüsü yalnızca başarısızlıkta
    screenshot: 'only-on-failure',
    
    // Video kayıt ayarları
    video: 'on-first-retry',
    
    // Tarayıcı ayarları
    viewport: { width: 1280, height: 720 },
    
    // Test artefaktları klasörü
    recordVideo: {
      dir: './test-results/videos/',
      size: { width: 1280, height: 720 },
    },
  },

  /* Konfigüre edilmiş projeler */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Paralel çalışırsa, ikinci sıradaki test bozulabilir
    // Test verilerinin diğer tarayıcılara karşı izole edildiğinden emin olun
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // Mobil tarayıcı testleri
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 5'] },
    }
  ],

  /* Local development server konfigürasyonu */
  webServer: {
    command: 'cd .. && npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
  
  /* Artefact dizini */
  outputDir: './test-results/',
}); 