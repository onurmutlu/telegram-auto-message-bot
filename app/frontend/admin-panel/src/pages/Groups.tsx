import { useState } from 'react'
import { Icon } from '@iconify/react'

// Geçici grup verisi
const mockGroups = [
  { 
    id: 1, 
    name: 'Teknoloji Sohbetleri', 
    memberCount: 128, 
    isActive: true, 
    lastActivity: '2023-05-15T10:30:00Z', 
    description: 'Teknoloji ve yazılım hakkında konuştuğumuz grup',
    type: 'public'
  },
  { 
    id: 2, 
    name: 'Proje Takımı', 
    memberCount: 42, 
    isActive: true, 
    lastActivity: '2023-05-15T14:20:00Z', 
    description: 'X Projesi için oluşturulan takım grubu',
    type: 'private'
  },
  { 
    id: 3, 
    name: 'Oyun Kulübü', 
    memberCount: 85, 
    isActive: false, 
    lastActivity: '2023-05-10T08:45:00Z', 
    description: 'Video oyunları tartışma platformu',
    type: 'public'
  },
  { 
    id: 4, 
    name: 'Kitap Okuma Kulübü', 
    memberCount: 64, 
    isActive: true, 
    lastActivity: '2023-05-14T19:15:00Z', 
    description: 'Aylık kitap önerileri ve tartışmaları',
    type: 'private'
  },
  { 
    id: 5, 
    name: 'Duyuru Kanalı', 
    memberCount: 210, 
    isActive: true, 
    lastActivity: '2023-05-16T11:30:00Z', 
    description: 'Resmi duyuruların yapıldığı kanal',
    type: 'channel'
  }
]

const Groups = () => {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedFilter, setSelectedFilter] = useState('all') // 'all', 'active', 'inactive'
  
  // API bağlandığında bu kodu aktifleştirin
  // const { data: groups, isLoading, isError } = useQuery({
  //   queryKey: ['groups'],
  //   queryFn: getGroups
  // })
  
  // Şimdilik mock veriyi kullanıyoruz
  const groups = mockGroups
  const isLoading = false
  const isError = false
  
  // Grupları filtrele
  const filteredGroups = groups
    .filter(group => 
      group.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.description.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .filter(group => {
      if (selectedFilter === 'all') return true
      if (selectedFilter === 'active') return group.isActive
      if (selectedFilter === 'inactive') return !group.isActive
      return true
    })
  
  // Grup tipine göre ikon belirle
  const getGroupIcon = (type: string) => {
    switch (type) {
      case 'private':
        return 'tabler:lock'
      case 'channel':
        return 'tabler:broadcast'
      case 'public':
      default:
        return 'tabler:users-group'
    }
  }
  
  return (
    <div className="container mx-auto">
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Gruplar</h2>
          <div className="flex space-x-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Grup ara..."
                className="input pr-10"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
              <Icon 
                icon="tabler:search" 
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400"
              />
            </div>
            <select 
              className="input"
              value={selectedFilter}
              onChange={e => setSelectedFilter(e.target.value)}
            >
              <option value="all">Tüm Gruplar</option>
              <option value="active">Aktif Gruplar</option>
              <option value="inactive">Pasif Gruplar</option>
            </select>
            <button className="btn btn-primary flex items-center space-x-1">
              <Icon icon="tabler:refresh" />
              <span>Yenile</span>
            </button>
          </div>
        </div>
        
        {isLoading ? (
          <div className="h-64 flex justify-center items-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-700"></div>
          </div>
        ) : isError ? (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <strong className="font-bold">Hata!</strong>
            <span className="block sm:inline"> Gruplar yüklenirken bir hata oluştu.</span>
          </div>
        ) : filteredGroups.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Icon icon="tabler:users-off" className="text-6xl mx-auto mb-4 text-gray-300" />
            <p>Grup bulunamadı</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredGroups.map((group) => (
              <div key={group.id} className="card-hover">
                <div className="flex items-start">
                  <div className={`p-3 rounded-full mr-3 ${group.isActive ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'}`}>
                    <Icon icon={getGroupIcon(group.type)} className="text-xl" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h3 className="font-medium text-gray-900">{group.name}</h3>
                      <span className={`badge ${group.isActive ? 'badge-success' : 'badge-error'}`}>
                        {group.isActive ? 'Aktif' : 'Pasif'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-1 line-clamp-2">{group.description}</p>
                    <div className="text-xs text-gray-500 mt-2 flex justify-between">
                      <span>{group.memberCount} üye</span>
                      <span>Son aktivite: {new Date(group.lastActivity).toLocaleDateString('tr-TR')}</span>
                    </div>
                    <div className="mt-3 flex justify-end space-x-2">
                      <button className="p-1 hover:bg-gray-100 rounded">
                        <Icon icon="tabler:eye" className="text-blue-600" />
                      </button>
                      <button className="p-1 hover:bg-gray-100 rounded">
                        <Icon icon="tabler:message" className="text-green-600" />
                      </button>
                      <button className="p-1 hover:bg-gray-100 rounded">
                        <Icon icon="tabler:settings" className="text-gray-600" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Groups; 