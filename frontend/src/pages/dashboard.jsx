import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/sidebar";
import { API_BASE_URL } from "../api";


const endpoints = [
  ["POST", "/auth/register", "Public registration"],
  ["POST", "/auth/login", "Public login"],
  ["POST", "/auth/forgot-password", "Password recovery question"],
  ["POST", "/auth/reset-password", "Reset password"],
  ["GET", "/auth/me", "Current approved account"],
  ["GET", "/employees", "Role-filtered employee list"],
  ["POST", "/employees", "Admin only"],
  ["GET", "/employees/{employee_id}", "Role-filtered employee detail"],
  ["PATCH", "/employees/{employee_id}", "Admin or own permitted fields"],
  ["DELETE", "/employees/{employee_id}", "Admin only"],
  ["GET/POST/PATCH/DELETE", "/divisions", "Master CRUD"],
  ["GET/POST/PATCH/DELETE", "/departments", "Master CRUD"],
  ["GET/POST/PATCH/DELETE", "/designations", "Master CRUD"],
  ["GET/POST/PATCH/DELETE", "/locations", "Master CRUD"],
  ["GET/POST/PATCH/DELETE", "/office-addresses", "Master CRUD"],
  ["GET/PATCH", "/admin/users", "Admin user management"],
  ["POST", "/admin/users/{user_id}/approve", "Admin approval"],
  ["POST", "/admin/users/{user_id}/reject", "Admin rejection"],
];


function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  const [users, setUsers] = useState([]);
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
      if (activeItem === "Users" && user.role === "admin") {
        const response = await fetch(`${API_BASE_URL}/admin/users?limit=100`, { headers: { Authorization: `Bearer ${token}` } });
        if (response.ok) setUsers(await response.json());
      }
      if (activeItem === "My Profile" && user.employee_id) {
        const response = await fetch(`${API_BASE_URL}/employees/${user.employee_id}`, { headers: { Authorization: `Bearer ${token}` } });
        if (response.ok) setProfile(await response.json());
      }
    }
    loadSection();
  }, [activeItem, token, user]);

  async function updateApproval(userId, action) {
    setError("");
    const response = await fetch(`${API_BASE_URL}/admin/users/${userId}/${action}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json();
    if (!response.ok) {
      setError(data.detail || "Account approval could not be updated");
      return;
    }
    setUsers((current) => current.map((item) => item.id === userId ? data : item));
  }

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
        {activeItem === "API Endpoints" ? <EndpointDirectory role={user.role} /> : activeItem === "Users" && user.role === "admin" ? <UserApprovals users={users} onAction={updateApproval} /> : activeItem === "My Profile" ? <Profile profile={profile} /> : <section className="dashboard-card"><span>{activeItem}</span><h2>{activeItem}</h2><p>{sectionDescription(user.role, activeItem)}</p></section>}
      </main>
    </div>
  );
}


function EndpointDirectory({ role }) {
  return <section className="dashboard-card endpoint-card"><span>API Directory</span><h2>Available API endpoints</h2><p>Interactive request testing remains available in FastAPI Swagger at <a href={`${API_BASE_URL}/docs`} target="_blank" rel="noreferrer">/docs</a>.</p><div className="endpoint-list">{endpoints.filter(([, path]) => role === "admin" || !path.startsWith("/admin")).map(([method, path, access]) => <div className="endpoint-row" key={`${method}-${path}`}><strong>{method}</strong><code>{path}</code><small>{access}</small></div>)}</div></section>;
}


function UserApprovals({ users, onAction }) {
  return <section className="dashboard-card wide-card"><span>Administration</span><h2>Registration approvals</h2><div className="user-list">{users.map((user) => <div className="user-row" key={user.id}><div><strong>{user.username}</strong><small>Employee ID: {user.employee_id ?? "Not linked"}</small></div><em className={`status ${user.approval_status}`}>{user.approval_status}</em>{user.approval_status !== "approved" && <button onClick={() => onAction(user.id, "approve")}>Approve</button>}{user.approval_status !== "rejected" && <button className="reject-button" onClick={() => onAction(user.id, "reject")}>Reject</button>}</div>)}</div></section>;
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
