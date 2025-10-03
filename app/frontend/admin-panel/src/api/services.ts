import axios from 'axios'

// API'nin çalıştığı adresi kullan
const API_URL = '/api/v1'
const USE_MOCK_DATA = false // Gerçek API hazır olmadığında geçici olarak mock verileri kullan

// Hata ayıklama için Axios interceptors ekle
axios.interceptors.request.use(config => {
  console.log(`${config.method?.toUpperCase()} isteği: ${config.url}`)
  return config
})

axios.interceptors.response.use(
  response => {
    console.log(`İstek başarılı: ${response.config.url}`)
    return response
  },
  error => {
    console.error(`İstek hatası: ${error.config?.url}`, error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export type Service = {
  name: string
  status: string
  running: boolean
  healthy: boolean
  uptime: number
  last_error: string | null
  depends_on: string[]
}

export type ServiceStatusResponse = {
  status: string
  message: string
  details: Record<string, string>
}

export type HealthData = {
  status: string
  all_healthy: boolean
  services: Record<string, {
    status: string
    running: boolean
    healthy: boolean
    uptime: number
    last_error: string | null
  }>
}

// Mock veriler
const mockServices: Service[] = [
  {
    name: 'telegram_client',
    status: 'running',
    running: true,
    healthy: true,
    uptime: 1200,
    last_error: null,
    depends_on: ['database']
  },
  {
    name: 'database',
    status: 'running',
    running: true,
    healthy: true,
    uptime: 3600,
    last_error: null,
    depends_on: []
  },
  {
    name: 'api_server',
    status: 'warning',
    running: true,
    healthy: false,
    uptime: 600,
    last_error: 'Bağlantı sorunu',
    depends_on: ['database']
  },
  {
    name: 'message_handler',
    status: 'stopped',
    running: false,
    healthy: false,
    uptime: 0,
    last_error: 'Servis çalışmıyor',
    depends_on: ['telegram_client']
  }
]

const mockHealthData: HealthData = {
  status: 'warning',
  all_healthy: false,
  services: {
    telegram_client: {
      status: 'running',
      running: true,
      healthy: true,
      uptime: 1200,
      last_error: null
    },
    database: {
      status: 'running',
      running: true,
      healthy: true,
      uptime: 3600,
      last_error: null
    },
    api_server: {
      status: 'warning',
      running: true,
      healthy: false,
      uptime: 600,
      last_error: 'Bağlantı sorunu'
    },
    message_handler: {
      status: 'stopped',
      running: false,
      healthy: false,
      uptime: 0,
      last_error: 'Servis çalışmıyor'
    }
  }
}

// Tüm servisleri getir
export const getServices = async (): Promise<Service[]> => {
  if (USE_MOCK_DATA) {
    console.log('Mock veri kullanılıyor: getServices')
    return mockServices
  }

  try {
    const response = await axios.get<Service[]>(`${API_URL}/services`)
    return response.data
  } catch (error) {
    console.error('Servisler alınırken hata:', error)
    throw error
  }
}

// Belirli bir servisi getir
export const getService = async (serviceName: string): Promise<Service> => {
  if (USE_MOCK_DATA) {
    console.log(`Mock veri kullanılıyor: getService(${serviceName})`)
    const service = mockServices.find(s => s.name === serviceName)
    if (service) return service
    throw new Error('Servis bulunamadı')
  }

  try {
    const response = await axios.get<Service>(`${API_URL}/services/${serviceName}`)
    return response.data
  } catch (error) {
    console.error(`Servis alınırken hata (${serviceName}):`, error)
    throw error
  }
}

// Servisleri başlat
export const startService = async (serviceNames: string[]): Promise<ServiceStatusResponse> => {
  if (USE_MOCK_DATA) {
    console.log(`Mock veri kullanılıyor: startService(${serviceNames.join(', ')})`)
    return {
      status: 'success',
      message: 'Servisler başlatıldı',
      details: serviceNames.reduce((acc, name) => ({...acc, [name]: 'started'}), {})
    }
  }

  try {
    const response = await axios.post<ServiceStatusResponse>(`${API_URL}/services/start`, {
      services: serviceNames
    })
    return response.data
  } catch (error) {
    console.error('Servisler başlatılırken hata:', error)
    throw error
  }
}

// Servisleri durdur
export const stopService = async (serviceNames: string[], force = false): Promise<ServiceStatusResponse> => {
  if (USE_MOCK_DATA) {
    console.log(`Mock veri kullanılıyor: stopService(${serviceNames.join(', ')}, ${force})`)
    return {
      status: 'success',
      message: 'Servisler durduruldu',
      details: serviceNames.reduce((acc, name) => ({...acc, [name]: 'stopped'}), {})
    }
  }

  try {
    const response = await axios.post<ServiceStatusResponse>(`${API_URL}/services/stop`, {
      services: serviceNames,
      force
    })
    return response.data
  } catch (error) {
    console.error('Servisler durdurulurken hata:', error)
    throw error
  }
}

// Servis yeniden başlat
export const restartService = async (serviceName: string): Promise<ServiceStatusResponse> => {
  if (USE_MOCK_DATA) {
    console.log(`Mock veri kullanılıyor: restartService(${serviceName})`)
    return {
      status: 'success',
      message: `${serviceName} servisi yeniden başlatıldı`,
      details: {[serviceName]: 'restarted'}
    }
  }

  try {
    const response = await axios.post<ServiceStatusResponse>(`${API_URL}/services/${serviceName}/restart`)
    return response.data
  } catch (error) {
    console.error(`Servis yeniden başlatılırken hata (${serviceName}):`, error)
    throw error
  }
}

// Servis sağlık durumlarını getir
export const getServicesHealth = async (): Promise<HealthData> => {
  if (USE_MOCK_DATA) {
    console.log('Mock veri kullanılıyor: getServicesHealth')
    return mockHealthData
  }

  try {
    const response = await axios.get<HealthData>(`${API_URL}/services/health`)
    return response.data
  } catch (error) {
    console.error('Servis sağlık durumları alınırken hata:', error)
    throw error
  }
} 