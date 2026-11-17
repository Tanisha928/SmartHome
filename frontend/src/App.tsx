import type { ReactNode } from "react";
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Icon, type IconName } from "./components/Icon";
import { AlertDashboard } from "./features/alerts";
import { Login } from "./routes/Login";
import { OwnerProfile } from "./routes/OwnerProfile";
import { Signup } from "./routes/Signup";
import { RouteGuard } from "./components/RouteGuard";
import { useAuthStore } from "./stores/authStore";
import { AdminLive } from "./routes/AdminLive";
import { AdminHistory } from "./routes/AdminHistory";
import { Settings } from "./routes/Settings";
import { OwnerHome } from "./routes/OwnerHome";
import { OwnerHistory } from "./routes/OwnerHistory";
import { DeviceManagement, FleetView, MyDevices } from "./features/devices";
import { AuditLog, DataHealth, EventPipeline, InferenceExplorer, RetentionBackup } from "./features/dataops";

function Shell({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const home = user?.role === "admin" ? "/admin" : "/owner";
  // Tokens live in memory, so typed URLs reload the app and sign you out: every screen needs a link.
  const dataLinks = [["health", "Health"], ["events", "Event pipeline"], ["inference", "Inference"], ["audit", "Audit log"], ["retention", "Retention"]] as const;
  const subnav = user?.role === "admin" && pathname.startsWith("/admin/data") ? <nav className="app-subnav" aria-label="Data operations">{dataLinks.map(([path, label]) => <NavLink key={path} to={`/admin/data/${path}`}>{label}</NavLink>)}</nav> : null;
  const admin = user?.role === "admin";
  const links: Array<[string, string, IconName]> = admin
    ? [["/admin", "Live alerts", "activity"], ["/admin/history", "History", "history"], ["/admin/devices", "Devices", "devices"], ["/admin/fleet", "Fleet", "fleet"], ["/admin/data/health", "Data", "data"], ["/admin/analytics", "Alert analytics", "activity"], ["/admin/settings", "Settings", "settings"]]
    : [["/owner", "Home", "home"], ["/owner/history", "History", "history"], ["/owner/devices", "My devices", "devices"], ["/owner/profile", "Profile", "profile"]];
  const name = user?.name ?? user?.full_name ?? user?.email ?? "Your account";
  return <div className="workspace"><a className="skip-link" href="#workspace-content">Skip to content</a><aside className="sidebar"><Link className="brand" to={home}><span className="brand-mark"><Icon name="home" size={23} /></span><span>Smart Home<small>CONNECTED LIVING</small></span></Link><div className="workspace-label">{admin ? "OPERATIONS WORKSPACE" : "YOUR HOME"}</div><nav className="sidebar-links" aria-label="Main navigation">{links.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === home} className={({ isActive }) => isActive || label === "Data" && pathname.startsWith("/admin/data") ? "active" : ""}><Icon name={icon} /><span>{label}</span></NavLink>)}</nav><div className="sidebar-footer"><Icon name="shield" /><p>Care, always connected.<small>One place for your home's activity.</small></p></div><div className="account-block"><span className="avatar">{name.charAt(0).toUpperCase()}</span><div><strong>{name}</strong><small>{admin ? "Administrator" : "Homeowner"}</small></div><button className="nav-logout" onClick={() => { void logout().then(() => navigate("/login")); }} aria-label="Sign out"><Icon name="arrow" /></button></div></aside><div className="workspace-main"><header className="workspace-top"><div><span className="workspace-breadcrumb">Workspace</span><span className="breadcrumb-separator">/</span><strong>{links.find(([to]) => to === pathname)?.[1] ?? "Data operations"}</strong></div></header><main id="workspace-content" className="workspace-content">{subnav}{children}</main><footer className="workspace-footer"><span>Smart Home Platform</span><span>Built for peace of mind.</span></footer></div></div>;
}

function Dashboard({ role }: { role: "admin" | "owner" }) { const user = useAuthStore((state) => state.user); return <Shell><AlertDashboard role={role} houseId={user?.house_ids[0] ?? 1} /></Shell>; }
function AppRoutes() { const user = useAuthStore((state) => state.user); const houseId = user?.house_ids[0] ?? 1; return <Routes><Route path="/login" element={<Login />} /><Route path="/signup" element={<Signup />} /><Route element={<RouteGuard role="admin" />}><Route path="/admin" element={<Shell><AdminLive houseId={houseId} /></Shell>} /><Route path="/admin/history" element={<Shell><AdminHistory houseId={houseId} /></Shell>} /><Route path="/admin/settings" element={<Shell><Settings /></Shell>} /><Route path="/admin/devices" element={<Shell><DeviceManagement /></Shell>} /><Route path="/admin/fleet" element={<Shell><FleetView /></Shell>} /><Route path="/admin/data/health" element={<Shell><DataHealth /></Shell>} /><Route path="/admin/data/events" element={<Shell><EventPipeline /></Shell>} /><Route path="/admin/data/inference" element={<Shell><InferenceExplorer /></Shell>} /><Route path="/admin/data/audit" element={<Shell><AuditLog /></Shell>} /><Route path="/admin/data/retention" element={<Shell><RetentionBackup /></Shell>} /><Route path="/admin/*" element={<Dashboard role="admin" />} /></Route><Route element={<RouteGuard role="owner" />}><Route path="/owner" element={<Shell><OwnerHome houseId={houseId} /></Shell>} /><Route path="/owner/history" element={<Shell><OwnerHistory houseId={houseId} /></Shell>} /><Route path="/owner/devices" element={<Shell><MyDevices houseId={houseId} /></Shell>} /><Route path="/owner/profile" element={<Shell><OwnerProfile houseId={houseId} /></Shell>} /></Route><Route path="*" element={<Navigate to="/admin" replace />} /></Routes>; }
export default function App() { return <BrowserRouter><AppRoutes /></BrowserRouter>; }
