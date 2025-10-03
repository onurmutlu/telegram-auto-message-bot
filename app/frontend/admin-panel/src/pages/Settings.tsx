import { useState } from 'react'
import { Icon } from '@iconify/react'

const Settings = () => {
  const [generalSettings, setGeneralSettings] = useState({
    botName: 'TelegramBot',
    defaultLanguage: 'tr',
    timeZone: 'Europe/Istanbul',
    autoReply: true,
    adminNotifications: true,
    loggingLevel: 'info'
  })
  
  const [notificationSettings, setNotificationSettings] = useState({
    errorNotifications: true,
    userJoinNotifications: true,
    messageNotifications: false,
    maintenanceAlerts: true,
    emailNotifications: false
  })
  
  const [securitySettings, setSecuritySettings] = useState({
    twoFactorAuth: false,
    ipRestriction: false,
    allowedIPs: '',
    sessionTimeout: 30
  })
  
  // Form gönderimi
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // Burada ayarları API'ye gönderme işlemi olacak
    console.log('Ayarlar kaydedildi:', {
      generalSettings,
      notificationSettings,
      securitySettings
    })
    
    // Başarı mesajı göster
    alert('Ayarlar başarıyla kaydedildi.')
  }
  
  return (
    <div className="container mx-auto">
      <form onSubmit={handleSubmit}>
        {/* Genel Ayarlar */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Genel Ayarlar</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bot Adı
              </label>
              <input
                type="text"
                className="input w-full"
                value={generalSettings.botName}
                onChange={(e) => setGeneralSettings({...generalSettings, botName: e.target.value})}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Varsayılan Dil
              </label>
              <select
                className="input w-full"
                value={generalSettings.defaultLanguage}
                onChange={(e) => setGeneralSettings({...generalSettings, defaultLanguage: e.target.value})}
              >
                <option value="tr">Türkçe</option>
                <option value="en">İngilizce</option>
                <option value="de">Almanca</option>
                <option value="fr">Fransızca</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Zaman Dilimi
              </label>
              <select
                className="input w-full"
                value={generalSettings.timeZone}
                onChange={(e) => setGeneralSettings({...generalSettings, timeZone: e.target.value})}
              >
                <option value="Europe/Istanbul">Türkiye (UTC+3)</option>
                <option value="Europe/London">Londra (UTC+0)</option>
                <option value="America/New_York">New York (UTC-5)</option>
                <option value="Asia/Tokyo">Tokyo (UTC+9)</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Log Seviyesi
              </label>
              <select
                className="input w-full"
                value={generalSettings.loggingLevel}
                onChange={(e) => setGeneralSettings({...generalSettings, loggingLevel: e.target.value})}
              >
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="autoReply"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={generalSettings.autoReply}
                onChange={(e) => setGeneralSettings({...generalSettings, autoReply: e.target.checked})}
              />
              <label htmlFor="autoReply" className="text-sm font-medium text-gray-700">
                Otomatik Yanıtlama
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="adminNotifications"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={generalSettings.adminNotifications}
                onChange={(e) => setGeneralSettings({...generalSettings, adminNotifications: e.target.checked})}
              />
              <label htmlFor="adminNotifications" className="text-sm font-medium text-gray-700">
                Yönetici Bildirimleri
              </label>
            </div>
          </div>
        </div>
        
        {/* Bildirim Ayarları */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Bildirim Ayarları</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="errorNotifications"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={notificationSettings.errorNotifications}
                onChange={(e) => setNotificationSettings({...notificationSettings, errorNotifications: e.target.checked})}
              />
              <label htmlFor="errorNotifications" className="text-sm font-medium text-gray-700">
                Hata Bildirimleri
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="userJoinNotifications"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={notificationSettings.userJoinNotifications}
                onChange={(e) => setNotificationSettings({...notificationSettings, userJoinNotifications: e.target.checked})}
              />
              <label htmlFor="userJoinNotifications" className="text-sm font-medium text-gray-700">
                Kullanıcı Katılım Bildirimleri
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="messageNotifications"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={notificationSettings.messageNotifications}
                onChange={(e) => setNotificationSettings({...notificationSettings, messageNotifications: e.target.checked})}
              />
              <label htmlFor="messageNotifications" className="text-sm font-medium text-gray-700">
                Mesaj Bildirimleri
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="maintenanceAlerts"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={notificationSettings.maintenanceAlerts}
                onChange={(e) => setNotificationSettings({...notificationSettings, maintenanceAlerts: e.target.checked})}
              />
              <label htmlFor="maintenanceAlerts" className="text-sm font-medium text-gray-700">
                Bakım Uyarıları
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="emailNotifications"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={notificationSettings.emailNotifications}
                onChange={(e) => setNotificationSettings({...notificationSettings, emailNotifications: e.target.checked})}
              />
              <label htmlFor="emailNotifications" className="text-sm font-medium text-gray-700">
                E-posta Bildirimleri
              </label>
            </div>
          </div>
        </div>
        
        {/* Güvenlik Ayarları */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Güvenlik Ayarları</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="twoFactorAuth"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={securitySettings.twoFactorAuth}
                onChange={(e) => setSecuritySettings({...securitySettings, twoFactorAuth: e.target.checked})}
              />
              <label htmlFor="twoFactorAuth" className="text-sm font-medium text-gray-700">
                İki Faktörlü Kimlik Doğrulama
              </label>
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                id="ipRestriction"
                className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-2"
                checked={securitySettings.ipRestriction}
                onChange={(e) => setSecuritySettings({...securitySettings, ipRestriction: e.target.checked})}
              />
              <label htmlFor="ipRestriction" className="text-sm font-medium text-gray-700">
                IP Kısıtlaması
              </label>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                İzin Verilen IP'ler (virgülle ayırın)
              </label>
              <input
                type="text"
                className="input w-full"
                placeholder="192.168.1.1, 10.0.0.1"
                value={securitySettings.allowedIPs}
                onChange={(e) => setSecuritySettings({...securitySettings, allowedIPs: e.target.value})}
                disabled={!securitySettings.ipRestriction}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Oturum Zaman Aşımı (dakika)
              </label>
              <input
                type="number"
                className="input w-full"
                min="5"
                max="1440"
                value={securitySettings.sessionTimeout}
                onChange={(e) => setSecuritySettings({...securitySettings, sessionTimeout: parseInt(e.target.value)})}
              />
            </div>
          </div>
        </div>
        
        {/* Kaydet Butonu */}
        <div className="flex justify-end mb-6">
          <button type="submit" className="btn btn-primary flex items-center space-x-2">
            <Icon icon="tabler:device-floppy" />
            <span>Ayarları Kaydet</span>
          </button>
        </div>
      </form>
    </div>
  )
}

export default Settings; 