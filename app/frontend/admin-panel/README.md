# Telegram Bot Yönetim Paneli

Bu proje, Telegram botunuzu yönetmek için kullanılan web tabanlı bir yönetim panelidir. Vite, React, UnoCSS ve React Query kullanılarak geliştirilmiştir.

## Özellikler

- Bot durumunu gerçek zamanlı izleme
- Servisleri başlatma, durdurma ve yeniden başlatma
- Mesajları görüntüleme ve yönetme
- Grup yönetimi
- Analitikler ve istatistikler
- Canlı log izleme

## Geliştirme

### Ön Koşullar

- Node.js (v18+)
- npm veya yarn
- Telegram Bot API sunucusu (localhost:8000)

### Kurulum

```bash
# Bağımlılıkları yükle
npm install

# Geliştirme sunucusunu başlat
npm run dev
```

### Üretim için Derleme

```bash
# Üretim için derleme
npm run build

# Derlenen dosyaları önizleme
npm run preview
```

### Yapılandırma

API sunucusu bağlantısını yapılandırmak için `vite.config.ts` dosyasını düzenleyin:

```ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000', // API sunucunuzun adresini buraya yazın
      changeOrigin: true,
    }
  }
}
```

## Proje Yapısı

```
src/
  ├── api/          # API bağlantı modülleri
  ├── assets/       # Statik dosyalar
  ├── components/   # Yeniden kullanılabilir komponentler
  ├── hooks/        # Özel React hooks
  ├── pages/        # Sayfa komponentleri
  └── utils/        # Yardımcı fonksiyonlar
```

## Teknolojiler

- [React](https://reactjs.org/) - UI kütüphanesi
- [Vite](https://vitejs.dev/) - Hızlı geliştirme sunucusu ve derleme aracı
- [UnoCSS](https://unocss.dev/) - Anlık, atomik CSS motoru
- [React Query](https://tanstack.com/query/latest) - Veri getirme ve önbelleğe alma
- [React Router](https://reactrouter.com/) - Sayfa yönlendirme
- [Axios](https://axios-http.com/) - API istekleri

## API Entegrasyonu

API'yi test etmek için:

```bash
# API bağlantısını test et
curl http://localhost:8000/api/health
```
