import { Icon } from '@iconify/react'

// Geçici istatistik verileri
const mockStats = {
  dailyMessages: [150, 230, 180, 250, 220, 300, 190],
  activeUsers: [80, 95, 88, 110, 105, 120, 100],
  newUsers: [12, 8, 15, 10, 7, 13, 9],
  totalStats: {
    totalMessages: 15320,
    totalUsers: 842,
    activeGroups: 25,
    avgResponseTime: 3.7
  }
}

const Analytics = () => {
  // Yüksek aktiviteli gruplar
  const topGroups = [
    { name: 'Teknoloji Sohbetleri', messages: 256, growth: '+12%' },
    { name: 'Proje Takımı', messages: 189, growth: '+5%' },
    { name: 'Duyuru Kanalı', messages: 145, growth: '+8%' },
    { name: 'Kitap Kulübü', messages: 120, growth: '-3%' },
  ]

  // Son 7 günün etiketleri
  const daysOfWeek = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
  
  return (
    <div className="container mx-auto">
      {/* Toplam İstatistikler */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow-md p-4">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-blue-100 text-blue-600 mr-4">
              <Icon icon="tabler:message-circle" className="text-xl" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Toplam Mesaj</p>
              <p className="text-xl font-semibold">{mockStats.totalStats.totalMessages.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-md p-4">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-green-100 text-green-600 mr-4">
              <Icon icon="tabler:users" className="text-xl" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Toplam Kullanıcı</p>
              <p className="text-xl font-semibold">{mockStats.totalStats.totalUsers.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-md p-4">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-purple-100 text-purple-600 mr-4">
              <Icon icon="tabler:users-group" className="text-xl" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Aktif Gruplar</p>
              <p className="text-xl font-semibold">{mockStats.totalStats.activeGroups}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-md p-4">
          <div className="flex items-center">
            <div className="p-3 rounded-full bg-amber-100 text-amber-600 mr-4">
              <Icon icon="tabler:clock" className="text-xl" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Ort. Yanıt Süresi</p>
              <p className="text-xl font-semibold">{mockStats.totalStats.avgResponseTime} dk</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Grafik ve Tablo */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Haftalık Aktivite</h2>
          <div className="h-64 flex items-end justify-between">
            {mockStats.dailyMessages.map((value, index) => (
              <div key={index} className="flex flex-col items-center">
                <div
                  className="bg-blue-500 w-10 rounded-t"
                  style={{ height: `${(value / 300) * 100}%` }}
                ></div>
                <div
                  className="bg-green-500 w-10 rounded-t mt-1"
                  style={{ height: `${(mockStats.activeUsers[index] / 120) * 100}%` }}
                ></div>
                <span className="text-xs text-gray-500 mt-2">{daysOfWeek[index].slice(0, 3)}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-center mt-2 text-sm">
            <div className="flex items-center mr-4">
              <div className="w-3 h-3 bg-blue-500 rounded mr-1"></div>
              <span>Mesajlar</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-green-500 rounded mr-1"></div>
              <span>Aktif Kullanıcılar</span>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Yüksek Aktiviteli Gruplar</h2>
          <div className="space-y-4">
            {topGroups.map((group, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="font-medium">{group.name}</div>
                <div className="flex items-center">
                  <span className="text-gray-500 mr-2">{group.messages}</span>
                  <span className={`text-xs ${group.growth.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                    {group.growth}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Kullanıcı Aktivitesi */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Kullanıcı Aktivitesi</h2>
          <select className="input">
            <option>Son 7 Gün</option>
            <option>Son 30 Gün</option>
            <option>Son 3 Ay</option>
          </select>
        </div>
        
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="py-2 px-4 text-left">Gün</th>
                <th className="py-2 px-4 text-right">Mesajlar</th>
                <th className="py-2 px-4 text-right">Aktif Kullanıcılar</th>
                <th className="py-2 px-4 text-right">Yeni Kullanıcılar</th>
              </tr>
            </thead>
            <tbody>
              {daysOfWeek.map((day, index) => (
                <tr key={index} className="border-b border-gray-100">
                  <td className="py-2 px-4">{day}</td>
                  <td className="py-2 px-4 text-right">{mockStats.dailyMessages[index]}</td>
                  <td className="py-2 px-4 text-right">{mockStats.activeUsers[index]}</td>
                  <td className="py-2 px-4 text-right">{mockStats.newUsers[index]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Analytics; 