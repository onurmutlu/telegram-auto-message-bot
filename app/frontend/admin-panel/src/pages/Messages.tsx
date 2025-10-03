import { useState } from 'react'
import { Icon } from '@iconify/react'

// Geçici mesaj verisi
const mockMessages = [
  { id: 1, text: 'Merhaba, nasılsınız?', sender: 'user123', timestamp: '2023-05-15T10:30:00Z', read: true },
  { id: 2, text: 'Bot hizmeti başlatıldı.', sender: 'system', timestamp: '2023-05-15T11:45:00Z', read: true },
  { id: 3, text: 'Yardıma ihtiyacım var.', sender: 'user456', timestamp: '2023-05-15T13:20:00Z', read: false },
  { id: 4, text: 'Grup oluşturuldu: TechTalk', sender: 'system', timestamp: '2023-05-16T09:10:00Z', read: false },
  { id: 5, text: 'Toplantı için hatırlatma.', sender: 'user789', timestamp: '2023-05-16T15:00:00Z', read: false },
]

const Messages = () => {
  const [searchTerm, setSearchTerm] = useState('')
  
  // API bağlandığında bu kodu aktifleştirin
  // const { data: messages, isLoading, isError } = useQuery({
  //   queryKey: ['messages'],
  //   queryFn: getMessages
  // })
  
  // Şimdilik mock veriyi kullanıyoruz
  const messages = mockMessages
  const isLoading = false
  const isError = false
  
  // Mesajları filtrele
  const filteredMessages = messages.filter(
    message => 
      message.text.toLowerCase().includes(searchTerm.toLowerCase()) ||
      message.sender.toLowerCase().includes(searchTerm.toLowerCase())
  )
  
  return (
    <div className="container mx-auto">
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Mesajlar</h2>
          <div className="flex space-x-2">
            <div className="relative">
              <input
                type="text"
                placeholder="Mesaj ara..."
                className="input pr-10"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
              />
              <Icon 
                icon="tabler:search" 
                className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400"
              />
            </div>
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
            <span className="block sm:inline"> Mesajlar yüklenirken bir hata oluştu.</span>
          </div>
        ) : filteredMessages.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <Icon icon="tabler:message-off" className="text-6xl mx-auto mb-4 text-gray-300" />
            <p>Mesaj bulunamadı</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Durum
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Gönderen
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Mesaj
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Tarih
                  </th>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    İşlemler
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredMessages.map((message) => (
                  <tr key={message.id} className={`hover:bg-gray-50 ${!message.read ? 'bg-blue-50' : ''}`}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center rounded-full w-2 h-2 ${message.read ? 'bg-gray-300' : 'bg-blue-500'}`}></span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {message.sender === 'system' ? (
                          <span className="flex items-center">
                            <Icon icon="tabler:robot" className="mr-1" />
                            Sistem
                          </span>
                        ) : message.sender}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">{message.text}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(message.timestamp).toLocaleString('tr-TR')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex space-x-2">
                        <button className="text-blue-600 hover:text-blue-900">
                          <Icon icon="tabler:eye" className="text-xl" />
                        </button>
                        <button className="text-red-600 hover:text-red-900">
                          <Icon icon="tabler:trash" className="text-xl" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default Messages; 