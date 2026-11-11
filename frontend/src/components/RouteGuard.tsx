import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "../stores/authStore";

export function RouteGuard({ role }: { role?: "admin" | "owner" }) {
  const { user } = useAuthStore();
  const location = useLocation();
  if (!user) return <Navigate to={`/login?return=${encodeURIComponent(location.pathname)}`} replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "admin" ? "/admin" : "/owner"} replace />;
  return <Outlet />;
}
