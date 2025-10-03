import { useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Icon } from '@iconify/react'

const Layout = () => {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const navItems = [
    { path: '/dashboard', label: 'Gösterge Paneli', icon: 'tabler:dashboard' },
    { path: '/services', label: 'Servisler', icon: 'tabler:server' },
    { path: '/messages', label: 'Mesajlar', icon: 'tabler:messages' },
    { path: '/groups', label: 'Gruplar', icon: 'tabler:users-group' },
    { path: '/analytics', label: 'Analitik', icon: 'tabler:chart-bar' },
    { path: '/settings', label: 'Ayarlar', icon: 'tabler:settings' },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Kenar çubuğu */}
      <div 
        className={`bg-blue-900 text-white transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-20'
        }`}
      >
        <div className="flex items-center justify-between p-4 border-b border-blue-800">
          <h1 className={`text-xl font-bold ${sidebarOpen ? 'block' : 'hidden'}`}>
            Telegram Bot
          </h1>
          <button 
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-blue-800"
          >
            <Icon icon={sidebarOpen ? 'tabler:chevron-left' : 'tabler:chevron-right'} className="text-xl" />
          </button>
        </div>
        <nav className="mt-4">
          <ul>
            {navItems.map((item) => (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`
                    flex items-center p-3 mx-2 my-1 rounded-lg transition-colors
                    ${isActive(item.path) 
                      ? 'bg-blue-700 text-white' 
                      : 'text-blue-100 hover:bg-blue-800'}
                  `}
                >
                  <Icon icon={item.icon} className="text-xl" />
                  {sidebarOpen && <span className="ml-3">{item.label}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      {/* Ana içerik */}
      <div className="flex-1 overflow-auto">
        <header className="bg-white shadow-md p-4">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800">
              {navItems.find(item => isActive(item.path))?.label || 'Gösterge Paneli'}
            </h2>
            <div className="flex items-center space-x-4">
              <button className="p-2 rounded-full hover:bg-gray-100">
                <Icon icon="tabler:bell" className="text-xl" />
              </button>
              <button className="p-2 rounded-full hover:bg-gray-100">
                <Icon icon="tabler:user-circle" className="text-xl" />
              </button>
            </div>
          </div>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default Layout 