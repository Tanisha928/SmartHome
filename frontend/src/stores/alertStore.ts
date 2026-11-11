import { create } from "zustand";
import type { Alert } from "../features/alerts/types";

type AlertEvent = { type: "alert.created" | "alert.updated"; alert: Alert };
type AlertState = { alerts: Alert[]; applyMessage: (event: AlertEvent, houseIds: number[]) => void; replace: (alerts: Alert[]) => void };

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  applyMessage: (event, houseIds) => set((state) => {
    if (!event?.alert || !houseIds.includes(event.alert.house_id)) return state;
    const existing = state.alerts.find((item) => item.alert_id === event.alert.alert_id);
    if (existing && existing.version >= event.alert.version) return state;
    const alerts = existing ? state.alerts.map((item) => item.alert_id === event.alert.alert_id ? event.alert : item) : [event.alert, ...state.alerts];
    return { alerts: alerts.slice(0, 200) };
  }),
  replace: (alerts) => set({ alerts: alerts.slice(0, 200) }),
}));
