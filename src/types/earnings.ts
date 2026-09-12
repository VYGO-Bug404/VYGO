export interface HourlyEarning {
  hour: number
  label: string
  earnings: number
  orders: number
}

export interface PlatformEarning {
  platform: string
  totalEarnings: number
  totalOrders: number
  earningsPerKm: number
  avgPerOrder: number
}

export interface EarningsSummary {
  total: number
  perHour: number
  perKm: number
  totalOrders: number
  changePercent: number
  activeMinutes: number
  totalKm: number
  hourly: HourlyEarning[]
  byPlatform: PlatformEarning[]
  bestHourRange: string
  bestHourEarnings: number
  additionalEarningsFromVygo: number
  kmSaved: number
  minutesSaved: number
}
