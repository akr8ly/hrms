import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { useEffect } from "react";

import Login from "./pages/login";
import Register from "./pages/register";
import Dashboard from "./pages/dashboard";
import ForgotPassword from "./pages/forgot-password";
import "./App.css";

function SessionExpiryListener() {
  const navigate = useNavigate();

  useEffect(() => {
    function redirectToLogin() {
      navigate("/login", {
        replace: true,
        state: { message: "Your session has expired. Please sign in again." },
      });
    }

    window.addEventListener("hrms:session-expired", redirectToLogin);
    return () => window.removeEventListener("hrms:session-expired", redirectToLogin);
  }, [navigate]);

  return null;
}

function App() {
  return (
    <BrowserRouter>
      <SessionExpiryListener />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />

        <Route
          path="/"
          element={<Navigate to="/login" replace />}
        />

        <Route
          path="*"
          element={<Navigate to="/login" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
