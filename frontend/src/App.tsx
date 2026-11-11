import { useState } from "react";
import { AlertDashboard } from "./features/alerts";
import type { AlertRole } from "./features/alerts/types";

export default function App() {
  const [role, setRole] = useState<AlertRole>("admin");
  const [houseId, setHouseId] = useState(1);
  return <><nav className="role-switcher"><span>Smart Home Platform</span><label>Preview role <select value={role} onChange={(event) => setRole(event.target.value as AlertRole)}><option value="admin">Administrator</option><option value="owner">Owner</option></select></label><label>House <input type="number" min="1" value={houseId} onChange={(event) => setHouseId(Number(event.target.value) || 1)} /></label></nav><AlertDashboard role={role} houseId={houseId} /></>;
}
