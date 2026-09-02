export interface DashboardOverview {
  total_devices: number
  online_devices: number
  offline_devices: number
  registered_devices: number
  isolated_devices: number
  quarantined_devices: number
  devices_with_inventory: number
  devices_without_inventory: number
  total_security_events: number
  latest_device_activity: string | null
}

export interface AuthToken {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: string
  username: string
  email: string
  is_active: boolean
  created_at: string
}

export interface DeviceSummary {
  id: string
  agent_id: string
  device_name: string | null
  hostname: string
  status: DeviceStatus
  last_seen: string | null
}

export interface DeviceListResponse {
  devices: DeviceSummary[]
  total: number
}

export interface DeviceInventory {
  id: string
  device_id: string
  hostname: string
  operating_system: string
  os_version: string | null
  architecture: string | null
  agent_version: string | null
  cpu_model: string | null
  cpu_cores: number | null
  total_memory_mb: number | null
  total_disk_mb: number | null
  local_ip: string | null
  mac_address: string | null
  cpu_info: Record<string, unknown> | null
  ram_info: Record<string, unknown> | null
  disk_info: Record<string, unknown> | null
  network_interfaces: Array<Record<string, unknown>> | null
  operating_system_info: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type SecurityEventType = 'PROCESS' | 'FILE' | 'REGISTRY' | 'NETWORK' | 'SYSTEM'
export type SecurityEventSeverity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export type GuardianXFeatureKey =
  | 'flow_duration'
  | 'forward_packet_count'
  | 'backward_packet_count'
  | 'forward_byte_count'
  | 'backward_byte_count'
  | 'packet_rate'
  | 'byte_rate'
  | 'is_one_way_flow'

export type SecurityEventMlFeatures = Partial<Record<GuardianXFeatureKey, number | boolean>>

export interface SecurityEventMlDetection {
  model: string
  schema_version: string
  prediction: number
  anomaly_score: number
  features?: SecurityEventMlFeatures
}

export interface SecurityEvent {
  id: string
  device_id: string
  event_type: SecurityEventType
  severity: SecurityEventSeverity
  source: string
  timestamp: string
  payload: Record<string, unknown> & {
    ml_detection?: SecurityEventMlDetection
  }
  created_at: string
}

export type DeviceStatus =
  | 'ONLINE'
  | 'OFFLINE'
  | 'REGISTERED'
  | 'ISOLATED'
  | 'QUARANTINED'
  | 'UNINSTALLED'

export type ConsoleState = 'checking' | 'authenticated' | 'authentication-required' | 'unavailable'
