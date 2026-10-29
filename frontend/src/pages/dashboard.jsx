import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/sidebar";
import HRChatbotWidget from "../components/chatbot";
import { apiFetch } from "../api";
import { readPhotoFile } from "../photoUpload";
import { EmployeesPage, MastersPage, UsersPage } from "../components/management";


function toPositiveEmployeeId(value) {
  const employeeId = Number(value);
  return Number.isSafeInteger(employeeId) && employeeId > 0 ? employeeId : null;
}


function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [activeItem, setActiveItem] = useState("Dashboard");
  const navigate = useNavigate();

  useEffect(() => {
    async function loadUser() {
      try {
        const response = await apiFetch("/auth/me");
        if (!response.ok) {
          navigate("/login");
          return;
        }
        setUser(await response.json());
      } catch {
        setError("Cannot connect to the HRMS API");
      }
    }
    void loadUser();
  }, [navigate]);

  useEffect(() => {
    async function loadSection() {
      if (!user) return;
      if (activeItem === "My Profile" && user.employee_id) {
        const employeeId = toPositiveEmployeeId(user.employee_id);
        if (employeeId === null) {
          setProfile(null);
          setError("Invalid employee profile reference.");
          return;
        }
        const response = await apiFetch(`/employees/${employeeId}`);
        if (response.ok) setProfile(await response.json());
      }
    }
    void loadSection();
  }, [activeItem, user]);

  async function logout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // Navigate even if the session has already expired or the API is unavailable.
    }
    navigate("/login");
  }

  if (error && !user) return <p className="error-message">{error}</p>;
  if (!user) return <p>Loading...</p>;

  return (
    <div className="app-layout">
      <Sidebar role={user.role} collapsed={collapsed} activeItem={activeItem} onSelect={setActiveItem} onToggle={() => setCollapsed(!collapsed)} />
      <main>
        <div className="page-header"><div><h1>HRMS Dashboard</h1><p>Welcome, {user.username}. Your role is {user.role}.</p></div><button className="logout-button" onClick={logout}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /></svg><span>Logout</span></button></div>
        {error && <p className="error-message">{error}</p>}
        {activeItem === "Employees" ? <EmployeesPage role={user.role} /> : activeItem === "Masters" && user.role === "admin" ? <MastersPage /> : activeItem === "Users" && user.role === "admin" ? <UsersPage /> : activeItem === "My Profile" ? <Profile profile={profile} onUpdate={setProfile} onPasswordChanged={logout} /> : <section className="dashboard-card"><span>{activeItem}</span><h2>{activeItem}</h2><p>{sectionDescription(user.role, activeItem)}</p></section>}
      </main>
      <HRChatbotWidget role={user.role} />
    </div>
  );
}


function Profile({ profile, onUpdate, onPasswordChanged }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ personal_email: "", phone_number: "", residential_address: "" });
  const [photo, setPhoto] = useState(null);
  const [photoSource, setPhotoSource] = useState(null);
  const [photoName, setPhotoName] = useState("");
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
    setPhotoName("");
    setMessage("");
    setEditing(true);
  }

  async function readPhoto(file) {
    if (!file) return;
    try {
      setPhotoSource(await readPhotoFile(file));
      setPhotoName(file.name);
      setMessage("");
    } catch (error) {
      setPhoto(null);
      setPhotoSource(null);
      setPhotoName("");
      setMessage(error.message);
    }
  }

  async function save(event) {
    event.preventDefault();
    const payload = { ...form };
    if (photo) payload.employee_photo = photo;
    const employeeId = toPositiveEmployeeId(profile.id);
    if (employeeId === null) {
      setMessage("Invalid employee profile reference.");
      return;
    }
    try {
      const response = await apiFetch(`/employees/${employeeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
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

  return <section className="dashboard-card profile-card"><span>Employee profile</span><div className="profile-summary">{profile.employee_photo ? <img className="profile-photo" src={profile.employee_photo} alt="Employee" /> : <div className="profile-placeholder">{profile.first_name[0]}{profile.last_name[0]}</div>}<div><h2>{profile.first_name} {profile.last_name}</h2><p>{profile.employee_code} · {profile.work_email}</p></div></div>{message && <p className="inline-message profile-message">{message}</p>}{editing ? <form className="profile-form" onSubmit={save}><label>Personal email<input type="email" required value={form.personal_email} onChange={(event) => setForm({ ...form, personal_email: event.target.value })} /></label><label>Phone number<input type="tel" required minLength="8" maxLength="20" value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} /></label><label>Residential address<textarea required maxLength="500" value={form.residential_address} onChange={(event) => setForm({ ...form, residential_address: event.target.value })} /></label><div className="photo-upload-field"><span>Replace photo</span><label className="file-picker"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { void readPhoto(event.target.files[0]); }} /><span className="file-picker-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 16.5V19a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2.5M8 9l4-4 4 4M12 5v11" /></svg>Choose image</span><span className="file-picker-name">{photoName || "PNG, JPG or WebP"}</span></label></div>{photoSource && <PhotoEditor source={photoSource} onChange={setPhoto} />}<div className="form-actions"><button className="icon-button" type="submit"><svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3h12l2 2v16H5z" /><path d="M8 3v6h8V3M8 21v-8h8v8" /></svg>Save profile</button><button type="button" className="secondary" onClick={() => setEditing(false)}>Cancel</button></div></form> : <div className="profile-details"><div><small>Personal email</small><strong>{profile.personal_email}</strong></div><div><small>Phone</small><strong>{profile.phone_number}</strong></div><div className="full-detail"><small>Residential address</small><strong>{profile.residential_address}</strong></div><button className="icon-button" onClick={beginEdit}><svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></svg>Edit profile</button></div>}<PasswordChange onChanged={onPasswordChanged} /></section>;
}


function PasswordChange({ onChanged }) {
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
      const response = await apiFetch("/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: form.current_password, new_password: form.new_password }),
      });
      const data = response.status === 204 ? null : await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data?.detail) ? data.detail.map((item) => item.msg).join(", ") : data?.detail;
        throw new Error(detail || "Password could not be changed");
      }
      onChanged();
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
