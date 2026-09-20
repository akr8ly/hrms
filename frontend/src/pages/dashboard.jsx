import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/sidebar";
import { API_BASE_URL } from "../api";
import { EmployeesPage, MastersPage, UsersPage } from "../components/management";


function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [activeItem, setActiveItem] = useState("Dashboard");
  const navigate = useNavigate();
  const token = localStorage.getItem("access_token");

  useEffect(() => {
    async function loadUser() {
      if (!token) {
        navigate("/login");
        return;
      }
      try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) {
          localStorage.removeItem("access_token");
          navigate("/login");
          return;
        }
        setUser(await response.json());
      } catch {
        setError("Cannot connect to the HRMS API");
      }
    }
    loadUser();
  }, [navigate, token]);

  useEffect(() => {
    async function loadSection() {
      if (!user) return;
      if (activeItem === "My Profile" && user.employee_id) {
        const response = await fetch(`${API_BASE_URL}/employees/${user.employee_id}`, { headers: { Authorization: `Bearer ${token}` } });
        if (response.ok) setProfile(await response.json());
      }
    }
    loadSection();
  }, [activeItem, token, user]);

  function logout() {
    localStorage.removeItem("access_token");
    navigate("/login");
  }

  if (error && !user) return <p className="error-message">{error}</p>;
  if (!user) return <p>Loading...</p>;

  return (
    <div className="app-layout">
      <Sidebar role={user.role} collapsed={collapsed} activeItem={activeItem} onSelect={setActiveItem} onToggle={() => setCollapsed(!collapsed)} />
      <main>
        <div className="page-header"><div><h1>HRMS Dashboard</h1><p>Welcome, {user.username}. Your role is {user.role}.</p></div><button onClick={logout}>Logout</button></div>
        {error && <p className="error-message">{error}</p>}
        {activeItem === "Employees" ? <EmployeesPage token={token} role={user.role} /> : activeItem === "Masters" && user.role === "admin" ? <MastersPage token={token} /> : activeItem === "Users" && user.role === "admin" ? <UsersPage token={token} /> : activeItem === "My Profile" ? <Profile profile={profile} /> : <section className="dashboard-card"><span>{activeItem}</span><h2>{activeItem}</h2><p>{sectionDescription(user.role, activeItem)}</p></section>}
      </main>
    </div>
  );
}


function Profile({ profile }) {
  if (!profile) return <section className="dashboard-card"><h2>My Profile</h2><p>No linked employee profile is available.</p></section>;
  return <section className="dashboard-card"><span>Employee profile</span>{profile.employee_photo && <img className="profile-photo" src={profile.employee_photo} alt="Employee" />}<h2>{profile.first_name} {profile.last_name}</h2><p>{profile.employee_code} · {profile.work_email}</p></section>;
}


function sectionDescription(role, item) {
  const descriptions = {
    Dashboard: "Your HRMS account is connected and ready to use.",
    Employees: role === "query" ? "You have read-only employee access with sensitive PII hidden." : "Manage employee records and employment details.",
    Masters: "Manage divisions, departments, designations, locations and offices.",
  };
  return descriptions[item] || "Select an HRMS section from the sidebar.";
}

export default Dashboard;
