import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/sidebar";
import { API_BASE_URL } from "../api";

function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [activeItem, setActiveItem] = useState("Dashboard");
  const navigate = useNavigate();

  useEffect(() => {
    async function loadUser() {
      const token = localStorage.getItem("access_token");

      if (!token) {
        navigate("/login");
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/auth/me`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }

        const data = await response.json();
        setUser(data);
      } catch {
        setError("Cannot connect to the HRMS API");
      }
    }

    loadUser();
  }, [navigate]);

  function logout() {
    localStorage.removeItem("access_token");
    navigate("/login");
  }

  if (error) {
    return <p className="error-message">{error}</p>;
  }

  if (!user) {
    return <p>Loading...</p>;
  }

  return (
    <div className="app-layout">
      <Sidebar
        role={user.role}
        collapsed={collapsed}
        activeItem={activeItem}
        onSelect={setActiveItem}
        onToggle={() => setCollapsed(!collapsed)}
      />

      <main>
        <div className="page-header">
          <div>
            <h1>HRMS Dashboard</h1>
            <p>
              Welcome, {user.username}. Your role is {user.role}.
            </p>
          </div>

          <button onClick={logout}>Logout</button>
        </div>

        <section className="dashboard-card">
          <span>{activeItem}</span>
          <h2>{activeItem}</h2>
          <p>{sectionDescription(user.role, activeItem)}</p>
        </section>
      </main>
    </div>
  );
}

function sectionDescription(role, item) {
  const descriptions = {
    Dashboard: "Your HRMS account is connected and ready to use.",
    Employees:
      role === "query"
        ? "You have read-only employee access with sensitive PII hidden."
        : "Manage employee records and employment details.",
    Masters: "Manage divisions, departments, designations, locations and offices.",
    Users: "Assign roles and connect user accounts to employee profiles.",
    "My Profile": "View and update the fields allowed on your employee profile.",
  };
  return descriptions[item] || "Select an HRMS section from the sidebar.";
}

export default Dashboard;
