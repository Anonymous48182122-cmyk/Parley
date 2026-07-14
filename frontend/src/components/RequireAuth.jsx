import { Navigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth();

  if (loading) return null; // avoid a flash-redirect while the session resolves
  if (!user) return <Navigate to="/auth" replace />;
  return children;
}
