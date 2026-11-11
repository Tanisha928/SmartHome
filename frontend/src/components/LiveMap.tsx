import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Alert } from "../features/alerts/types";
import type { House } from "../features/devices/types";
import { friendlyLabel } from "../lib/labels";
const colors = { critical: "#d84751", high: "#dd8a25", medium: "#b8931e", low: "#39a576" };
export function LiveMap({ alerts, house, onSelect }: { alerts: Alert[]; house: House | null; onSelect: (alert: Alert) => void }) { const latitude = house?.latitude ?? 47.6062; const longitude = house?.longitude ?? -122.3321; const center: LatLngExpression = [latitude, longitude]; return <MapContainer className="leaflet-map" center={center} zoom={12} scrollWheelZoom={false}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{alerts.map((alert, index) => <CircleMarker key={alert.alert_id} center={[latitude + ((index * 17) % 11) / 1000, longitude + ((index * 23) % 13) / 1000]} pathOptions={{ color: colors[alert.severity], fillColor: colors[alert.severity], fillOpacity: .8 }} radius={9} eventHandlers={{ click: () => onSelect(alert) }}><Popup>{friendlyLabel(alert.sound_type)} · Room {alert.room_id}</Popup></CircleMarker>)}</MapContainer>; }
