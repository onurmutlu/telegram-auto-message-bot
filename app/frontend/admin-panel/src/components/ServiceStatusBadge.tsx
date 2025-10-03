type ServiceStatusBadgeProps = {
  status: string
  running: boolean
  healthy: boolean
}

const ServiceStatusBadge = ({ status, running, healthy }: ServiceStatusBadgeProps) => {
  // Durum renklerini belirle
  let bgColor = "bg-gray-100"
  let textColor = "text-gray-800"
  let statusText = status || "Bilinmiyor"

  if (running && healthy) {
    bgColor = "bg-green-100"
    textColor = "text-green-800"
    statusText = "Çalışıyor"
  } else if (running && !healthy) {
    bgColor = "bg-yellow-100"
    textColor = "text-yellow-800"
    statusText = "Uyarı"
  } else if (!running) {
    bgColor = "bg-red-100"
    textColor = "text-red-800"
    statusText = "Durduruldu"
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor}`}>
      <span className={`w-2 h-2 mr-1.5 rounded-full ${running ? (healthy ? 'bg-green-500' : 'bg-yellow-500') : 'bg-red-500'}`}></span>
      {statusText}
    </span>
  )
}

export default ServiceStatusBadge 