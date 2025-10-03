import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Icon } from '@iconify/react';
import { getServices, startService, stopService, restartService } from '../api/services';
import ServiceStatusBadge from '../components/ServiceStatusBadge';

const Services = () => {
  const queryClient = useQueryClient();
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  
  // Servisleri getir
  const { data: services = [], isLoading, isError, error } = useQuery({
    queryKey: ['services'],
    queryFn: getServices,
    refetchInterval: 10000 // 10 saniyede bir yenile
  });

  // Servis başlatma
  const startMutation = useMutation({
    mutationFn: (serviceNames: string[]) => startService(serviceNames),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      setSelectedServices([]);
    }
  });

  // Servis durdurma
  const stopMutation = useMutation({
    mutationFn: (serviceNames: string[]) => stopService(serviceNames),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      setSelectedServices([]);
    }
  });

  // Servis yeniden başlatma
  const restartMutation = useMutation({
    mutationFn: (serviceName: string) => restartService(serviceName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
    }
  });

  // Servis seçme fonksiyonu
  const toggleServiceSelection = (serviceName: string) => {
    setSelectedServices(prev => 
      prev.includes(serviceName)
        ? prev.filter(name => name !== serviceName)
        : [...prev, serviceName]
    );
  };

  // Tüm servisleri seç/kaldır
  const toggleAllServices = () => {
    if (services.length > 0) {
      if (selectedServices.length === services.length) {
        setSelectedServices([]);
      } else {
        setSelectedServices(services.map(service => service.name));
      }
    }
  };

  // Yükleniyor gösterimi
  if (isLoading) {
    return (
      <div className="h-64 flex justify-center items-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-700"></div>
      </div>
    );
  }

  // Hata gösterimi
  if (isError) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative">
        <strong className="font-bold">Hata!</strong>
        <span className="block sm:inline"> {error instanceof Error ? error.message : 'Servisler yüklenirken bir hata oluştu.'}</span>
      </div>
    );
  }

  return (
    <div className="container mx-auto">
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Servisler</h2>
          <div className="flex space-x-2">
            <button 
              onClick={() => startMutation.mutate(selectedServices.length ? selectedServices : [])}
              disabled={startMutation.isPending}
              className="btn btn-success flex items-center space-x-1"
            >
              <Icon icon="tabler:player-play" />
              <span>{selectedServices.length ? 'Seçilenleri Başlat' : 'Tümünü Başlat'}</span>
            </button>
            <button 
              onClick={() => stopMutation.mutate(selectedServices.length ? selectedServices : [])}
              disabled={stopMutation.isPending}
              className="btn btn-danger flex items-center space-x-1"
            >
              <Icon icon="tabler:player-stop" />
              <span>{selectedServices.length ? 'Seçilenleri Durdur' : 'Tümünü Durdur'}</span>
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <input 
                    type="checkbox" 
                    checked={services.length > 0 && selectedServices.length === services.length}
                    onChange={toggleAllServices}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Servis
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Durum
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Çalışma Süresi
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Bağımlılıklar
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  İşlemler
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {services.map((service) => (
                <tr key={service.name} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <input 
                      type="checkbox" 
                      checked={selectedServices.includes(service.name)}
                      onChange={() => toggleServiceSelection(service.name)}
                      className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="text-sm font-medium text-gray-900">
                        {service.name}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <ServiceStatusBadge status={service.status} running={service.running} healthy={service.healthy} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {service.uptime ? `${Math.floor(service.uptime / 60)} dk ${service.uptime % 60} sn` : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {service.depends_on && service.depends_on.length > 0 
                      ? service.depends_on.join(', ') 
                      : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex space-x-2">
                      <button 
                        onClick={() => startMutation.mutate([service.name])}
                        disabled={startMutation.isPending}
                        className="text-green-600 hover:text-green-900"
                      >
                        <Icon icon="tabler:player-play" className="text-xl" />
                      </button>
                      <button 
                        onClick={() => stopMutation.mutate([service.name])}
                        disabled={stopMutation.isPending}
                        className="text-red-600 hover:text-red-900"
                      >
                        <Icon icon="tabler:player-stop" className="text-xl" />
                      </button>
                      <button 
                        onClick={() => restartMutation.mutate(service.name)}
                        disabled={restartMutation.isPending}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        <Icon icon="tabler:refresh" className="text-xl" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Services; 