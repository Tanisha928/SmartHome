import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Alert } from "../features/alerts/types";
import { friendlyLabel } from "../lib/labels";
const colors = { critical: "#d84751", high: "#dd8a25", medium: "#b8931e", low: "#39a576" };
export function LiveMap({ alerts, onSelect }: { alerts: Alert[]; onSelect: (alert: Alert) => void }) { const center: LatLngExpression = [47.6062, -122.3321]; return <MapContainer className="leaflet-map" center={center} zoom={12} scrollWheelZoom={false}><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{alerts.map((alert, index) => <CircleMarker key={alert.alert_id} center={[47.6062 + ((index * 17) % 11) / 1000, -122.3321 + ((index * 23) % 13) / 1000]} pathOptions={{ color: colors[alert.severity], fillColor: colors[alert.severity], fillOpacity: .8 }} radius={9} eventHandlers={{ click: () => onSelect(alert) }}><Popup>{friendlyLabel(alert.sound_type)} · Room {alert.room_id}</Popup></CircleMarker>)}</MapContainer>; }
