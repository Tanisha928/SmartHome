import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { AlertDashboard } from "./features/alerts";
import { Login } from "./routes/Login";
import { Signup } from "./routes/Signup";
import { RouteGuard } from "./components/RouteGuard";
import { useAuthStore } from "./stores/authStore";

function Shell({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const home = user?.role === "admin" ? "/admin" : "/owner";
  return <><nav className="app-nav"><Link className="brand" to={home}>Smart Home <span>●</span></Link><div className="nav-links">{user?.role === "admin" ? <><Link to="/admin">Live alerts</Link><Link to="/admin/history">History</Link><Link to="/admin/settings">Settings</Link></> : <><Link to="/owner">Home</Link><Link to="/owner/history">History</Link><Link to="/owner/profile">Profile</Link></>}</div><div className="nav-user"><span>{user?.full_name ?? user?.email}</span><button className="nav-logout" onClick={() => { void logout().then(() => navigate("/login")); }}>Sign out</button></div></nav>{children}</>;
}

function Dashboard({ role }: { role: "admin" | "owner" }) { const user = useAuthStore((state) => state.user); return <Shell><AlertDashboard role={role} houseId={user?.house_ids[0] ?? 1} /></Shell>; }
function AppRoutes() { return <Routes><Route path="/login" element={<Login />} /><Route path="/signup" element={<Signup />} /><Route element={<RouteGuard role="admin" />}><Route path="/admin" element={<Dashboard role="admin" />} /><Route path="/admin/history" element={<Dashboard role="admin" />} /><Route path="/admin/settings" element={<Dashboard role="admin" />} /></Route><Route element={<RouteGuard role="owner" />}><Route path="/owner" element={<Dashboard role="owner" />} /><Route path="/owner/history" element={<Dashboard role="owner" />} /><Route path="/owner/profile" element={<Dashboard role="owner" />} /></Route><Route path="*" element={<Navigate to="/admin" replace />} /></Routes>; }
export default function App() { return <BrowserRouter><AppRoutes /></BrowserRouter>; }
