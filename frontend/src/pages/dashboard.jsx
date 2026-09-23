import { useEffect, useRef, useState } from "react";
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
        {activeItem === "Employees" ? <EmployeesPage token={token} role={user.role} /> : activeItem === "Masters" && user.role === "admin" ? <MastersPage token={token} /> : activeItem === "Users" && user.role === "admin" ? <UsersPage token={token} /> : activeItem === "My Profile" ? <Profile profile={profile} token={token} onUpdate={setProfile} /> : <section className="dashboard-card"><span>{activeItem}</span><h2>{activeItem}</h2><p>{sectionDescription(user.role, activeItem)}</p></section>}
      </main>
    </div>
  );
}


function Profile({ profile, token, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ personal_email: "", phone_number: "", residential_address: "" });
  const [photo, setPhoto] = useState(null);
  const [photoSource, setPhotoSource] = useState(null);
  const [message, setMessage] = useState("");

  if (!profile) return <section className="dashboard-card"><h2>My Profile</h2><p>No linked employee profile is available.</p></section>;

  function beginEdit() {
    setForm({
      personal_email: profile.personal_email,
      phone_number: profile.phone_number,
      residential_address: profile.residential_address,
    });
    setPhoto(null);
    setPhotoSource(null);
    setMessage("");
    setEditing(true);
  }

  function readPhoto(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPhotoSource(reader.result);
    reader.readAsDataURL(file);
  }

  async function save(event) {
    event.preventDefault();
    const payload = { ...form };
    if (photo) payload.employee_photo = photo;
    try {
      const response = await fetch(`${API_BASE_URL}/employees/${profile.id}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Profile could not be updated");
      onUpdate(data);
      setEditing(false);
      setMessage("Profile updated successfully.");
    } catch (error) {
      setMessage(error.message);
    }
  }

  return <section className="dashboard-card profile-card"><span>Employee profile</span><div className="profile-summary">{profile.employee_photo ? <img className="profile-photo" src={profile.employee_photo} alt="Employee" /> : <div className="profile-placeholder">{profile.first_name[0]}{profile.last_name[0]}</div>}<div><h2>{profile.first_name} {profile.last_name}</h2><p>{profile.employee_code} · {profile.work_email}</p></div></div>{message && <p className="inline-message profile-message">{message}</p>}{editing ? <form className="profile-form" onSubmit={save}><label>Personal email<input type="email" required value={form.personal_email} onChange={(event) => setForm({ ...form, personal_email: event.target.value })} /></label><label>Phone number<input type="tel" required minLength="8" maxLength="20" value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} /></label><label>Residential address<textarea required maxLength="500" value={form.residential_address} onChange={(event) => setForm({ ...form, residential_address: event.target.value })} /></label><label>Replace photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => readPhoto(event.target.files[0])} /></label>{photoSource && <PhotoEditor source={photoSource} onChange={setPhoto} />}<div className="form-actions"><button type="submit">Save profile</button><button type="button" className="secondary" onClick={() => setEditing(false)}>Cancel</button></div></form> : <div className="profile-details"><div><small>Personal email</small><strong>{profile.personal_email}</strong></div><div><small>Phone</small><strong>{profile.phone_number}</strong></div><div className="full-detail"><small>Residential address</small><strong>{profile.residential_address}</strong></div><button onClick={beginEdit}>Edit profile</button></div>}<PasswordChange token={token} /></section>;
}


function PasswordChange({ token }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setMessage("");
    if (form.new_password !== form.confirm_password) {
      setFailed(true);
      setMessage("New passwords do not match.");
      return;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }),
      });
      const data = response.status === 204 ? null : await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data?.detail) ? data.detail.map((item) => item.msg).join(", ") : data?.detail;
        throw new Error(detail || "Password could not be changed");
      }
      setFailed(false);
      setMessage("Password changed successfully.");
      setForm({ current_password: "", new_password: "", confirm_password: "" });
      setOpen(false);
    } catch (error) {
      setFailed(true);
      setMessage(error.message);
    }
  }

  return <div className="password-panel"><div><h3>Password</h3><p>Use 7–15 characters with at least one digit and one special character.</p></div><button type="button" onClick={() => { setOpen(!open); setMessage(""); }}>{open ? "Cancel" : "Change password"}</button>{message && <p className={failed ? "error-message" : "success-message"}>{message}</p>}{open && <form onSubmit={submit}><label>Current password<input type="password" required autoComplete="current-password" value={form.current_password} onChange={(event) => setForm({ ...form, current_password: event.target.value })} /></label><label>New password<input type="password" required minLength="7" maxLength="15" autoComplete="new-password" value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} /></label><label>Confirm new password<input type="password" required minLength="7" maxLength="15" autoComplete="new-password" value={form.confirm_password} onChange={(event) => setForm({ ...form, confirm_password: event.target.value })} /></label><button type="submit">Update password</button></form>}</div>;
}


function PhotoEditor({ source, onChange }) {
  const canvasRef = useRef(null);
  const imageRef = useRef(null);
  const dragRef = useRef(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);

  useEffect(() => {
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      setPosition({ x: 0, y: 0 });
      setZoom(1);
      setRotation(0);
    };
    image.src = source;
  }, [source]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image) return;
    const context = canvas.getContext("2d");
    const size = canvas.width;
    const baseScale = Math.max(size / image.width, size / image.height);
    context.clearRect(0, 0, size, size);
    context.save();
    context.beginPath();
    context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
    context.clip();
    context.fillStyle = "#e2e8f0";
    context.fillRect(0, 0, size, size);
    context.translate(size / 2 + position.x, size / 2 + position.y);
    context.rotate(rotation * Math.PI / 180);
    context.scale(baseScale * zoom, baseScale * zoom);
    context.drawImage(image, -image.width / 2, -image.height / 2);
    context.restore();
    onChange(canvas.toDataURL("image/jpeg", 0.88));
  }, [position, zoom, rotation, source, onChange]);

  function pointerDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, startX: position.x, startY: position.y };
  }

  function pointerMove(event) {
    if (!dragRef.current) return;
    setPosition({
      x: dragRef.current.startX + event.clientX - dragRef.current.x,
      y: dragRef.current.startY + event.clientY - dragRef.current.y,
    });
  }

  return <div className="photo-editor"><div className="photo-crop-grid" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={() => { dragRef.current = null; }}><canvas ref={canvasRef} width="320" height="320" /></div><p>Drag the photo inside the circle to position it.</p><label>Zoom<input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label><label>Tilt<input type="range" min="-45" max="45" step="1" value={rotation} onChange={(event) => setRotation(Number(event.target.value))} /></label><div className="photo-editor-actions"><button type="button" onClick={() => setRotation((value) => value - 90)}>↶ Rotate</button><button type="button" onClick={() => setRotation((value) => value + 90)}>Rotate ↷</button><button type="button" onClick={() => { setPosition({ x: 0, y: 0 }); setZoom(1); setRotation(0); }}>Reset</button></div></div>;
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
