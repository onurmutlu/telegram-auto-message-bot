import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon } from '@iconify/react'
import { Link } from 'react-router-dom'
import { getServicesHealth } from '../api/services'
import ServiceStatusBadge from '../components/ServiceStatusBadge'

const Dashboard = () => {
  const [wsConnected, setWsConnected] = useState(false)
  const [wsError, setWsError] = useState<string | null>(null)
  const [logs, setLogs] = useState<{ message: string; timestamp: string; type: string }[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttempts = useRef(0)
  const MAX_RECONNECT_ATTEMPTS = 5
  
  // WebSocket bağlantısı kurma fonksiyonu
  const connectWebSocket = () => {
    // Eğer bağlantı zaten varsa, önce kapat
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close()
    }
    
    // WebSocket URL'sini oluştur
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsHost = window.location.host
    const wsUrl = `${wsProtocol}//${wsHost}/api/logs`
    
    console.log(`WebSocket bağlantısı kuruluyor: ${wsUrl}`)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
    
    // Bağlantı açıldığında
    ws.onopen = () => {
      console.log('WebSocket bağlantısı başarılı')
      setWsConnected(true)
      setWsError(null)
      reconnectAttempts.current = 0 // Bağlantı başarılı olduğunda denemeleri sıfırla
      
      // Sunucuya ping gönder (canlı bağlantıyı kontrol et)
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        } else {
          clearInterval(pingInterval)
        }
      }, 30000) // 30 saniyede bir ping gönder
    }
    
    // Mesaj alındığında
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setLogs((prevLogs) => {
          const newLogs = [...prevLogs, data]
          // Son 100 logu tut
          return newLogs.slice(-100)
        })
      } catch (e) {
        console.error('WebSocket mesajı ayrıştırılamadı:', e)
      }
    }
    
    // Bağlantı kapandığında
    ws.onclose = (event) => {
      console.warn(`WebSocket bağlantısı kapandı. Kod: ${event.code}`)
      setWsConnected(false)
      
      if (event.code !== 1000) { // 1000: Normal kapanış
        setWsError(`Bağlantı kesildi (${event.code})`)
        
        // Yeniden bağlanma denemesi
        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const timeout = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`${timeout}ms sonra yeniden bağlanmaya çalışılacak (${reconnectAttempts.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)
          
          if (reconnectTimeoutRef.current) {
            window.clearTimeout(reconnectTimeoutRef.current)
          }
          
          reconnectTimeoutRef.current = window.setTimeout(() => {
            reconnectAttempts.current++
            connectWebSocket()
          }, timeout)
        } else {
          setWsError('Yeniden bağlanma denemesi başarısız oldu.')
        }
      }
    }
    
    // Hata oluştuğunda
    ws.onerror = (event) => {
      console.error('WebSocket hatası:', event)
      setWsError('Bağlantı hatası')
    }
  }
  
  // Component mount olduğunda WebSocket bağlantısını kur
  useEffect(() => {
    connectWebSocket()
    
    // Component unmount olduğunda bağlantıyı ve zamanlayıcıları temizle
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])
  
  // Servislerin sağlık durumunu getir
  const { data: healthData, isLoading: healthLoading, error: healthError } = useQuery({
    queryKey: ['services-health'],
    queryFn: getServicesHealth,
    refetchInterval: 10000, // 10 saniyede bir yenile
    retry: 3
  })
  
  // İstatistik kartları
  const statsCards = [
    { title: 'Toplam Servis', value: healthData?.services ? Object.keys(healthData.services).length : '-', icon: 'tabler:server', color: 'bg-blue-500' },
    { title: 'Çalışan Servisler', value: healthData?.services ? Object.values(healthData.services).filter((s: any) => s.running).length : '-', icon: 'tabler:circle-check', color: 'bg-green-500' },
    { title: 'Duran Servisler', value: healthData?.services ? Object.values(healthData.services).filter((s: any) => !s.running).length : '-', icon: 'tabler:circle-x', color: 'bg-red-500' },
    { title: 'Uyarı Durumu', value: healthData?.services ? Object.values(healthData.services).filter((s: any) => s.running && !s.healthy).length : '-', icon: 'tabler:alert-triangle', color: 'bg-yellow-500' }
  ]
  
  return (
    <div className="container mx-auto">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        {statsCards.map((card, index) => (
          <div key={index} className="bg-white rounded-lg shadow-md p-4">
            <div className="flex items-center">
              <div className={`p-3 rounded-full ${card.color} text-white mr-4`}>
                <Icon icon={card.icon} className="text-xl" />
              </div>
              <div>
                <p className="text-sm text-gray-500">{card.title}</p>
                <p className="text-xl font-semibold">{card.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Servis Durumu ve Hızlı İşlemler */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Servis Durumu */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Servis Durumu</h2>
            <Link to="/services" className="text-blue-600 hover:text-blue-800 text-sm">
              Tüm Servisleri Görüntüle
            </Link>
          </div>
          
          {healthLoading ? (
            <div className="flex justify-center items-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-700"></div>
            </div>
          ) : healthError ? (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              <p className="font-bold">Hata!</p>
              <p>Servis bilgileri alınamadı. Lütfen API servisinin çalıştığından emin olun.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {healthData && healthData.services && Object.entries(healthData.services).map(([name, data]: [string, any]) => (
                <div key={name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center">
                    <ServiceStatusBadge status={data.status} running={data.running} healthy={data.healthy} />
                    <span className="ml-3 font-medium">{name}</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    {data.uptime ? `${Math.floor(data.uptime / 60)} dk ${data.uptime % 60} sn` : '-'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Hızlı İşlemler */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Hızlı İşlemler</h2>
          <div className="space-y-3">
            <Link to="/services" className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="p-2 rounded-full bg-blue-100 text-blue-600 mr-3">
                <Icon icon="tabler:server-cog" className="text-xl" />
              </div>
              <span>Servisleri Yönet</span>
            </Link>
            <Link to="/messages" className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="p-2 rounded-full bg-purple-100 text-purple-600 mr-3">
                <Icon icon="tabler:messages" className="text-xl" />
              </div>
              <span>Mesajları Görüntüle</span>
            </Link>
            <Link to="/groups" className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="p-2 rounded-full bg-green-100 text-green-600 mr-3">
                <Icon icon="tabler:users-group" className="text-xl" />
              </div>
              <span>Grupları Yönet</span>
            </Link>
            <Link to="/analytics" className="flex items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
              <div className="p-2 rounded-full bg-amber-100 text-amber-600 mr-3">
                <Icon icon="tabler:chart-bar" className="text-xl" />
              </div>
              <span>Analitikleri Görüntüle</span>
            </Link>
          </div>
        </div>
      </div>
      
      {/* Log Akışı */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Canlı Log Akışı</h2>
          <div className="flex items-center">
            <span className={`w-2 h-2 rounded-full mr-2 ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-sm text-gray-500">
              {wsConnected ? 'Bağlı' : wsError ? `Bağlantı sorunu: ${wsError}` : 'Bağlantı kesildi'}
            </span>
          </div>
        </div>
        
        <div className="bg-gray-800 text-gray-200 p-4 rounded-lg h-64 overflow-y-auto font-mono text-sm">
          {logs.length === 0 ? (
            <div className="flex justify-center items-center h-full text-gray-400">
              {wsConnected ? 'Log kaydı bekleniyor...' : 'WebSocket bağlantısı kurulamadı'}
            </div>
          ) : (
            logs.map((log, index) => (
              <div key={index} className={`mb-1 ${log.type === 'error' ? 'text-red-400' : log.type === 'warning' ? 'text-yellow-400' : 'text-gray-300'}`}>
                <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span> {log.message}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard 