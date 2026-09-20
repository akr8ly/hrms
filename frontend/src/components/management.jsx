import { useEffect, useState } from "react";
import { API_BASE_URL } from "../api";

const masterTypes = {
  divisions: { label: "Divisions", fields: ["code", "name", "description"] },
  departments: { label: "Departments", fields: ["code", "name", "description"] },
  designations: { label: "Designations", fields: ["code", "name", "description"] },
  locations: { label: "Locations", fields: ["code", "name", "description"] },
  "office-addresses": {
    label: "Office addresses",
    fields: ["address_line", "city", "state", "postal_code", "country", "location_id"],
  },
};

async function apiRequest(path, token, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(", ")
      : data.detail;
    throw new Error(detail || "Request failed");
  }
  return data;
}

function emptyFields(fields) {
  return Object.fromEntries(fields.map((field) => [field, ""]));
}

export function MastersPage({ token }) {
  const [type, setType] = useState("divisions");
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(emptyFields(masterTypes.divisions.fields));
  const [editingId, setEditingId] = useState(null);
  const [message, setMessage] = useState("");

  const config = masterTypes[type];

  async function load() {
    try {
      setRows(await apiRequest(`/${type}?limit=100`, token));
      setMessage("");
    } catch (error) {
      setMessage(error.message);
    }
  }

  useEffect(() => {
    setForm(emptyFields(masterTypes[type].fields));
    setEditingId(null);
    load();
  }, [type]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(event) {
    event.preventDefault();
    const payload = Object.fromEntries(
      Object.entries(form).map(([key, value]) => [key, key.endsWith("_id") ? Number(value) : value || null]),
    );
    try {
      await apiRequest(editingId ? `/${type}/${editingId}` : `/${type}`, token, {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setForm(emptyFields(config.fields));
      setEditingId(null);
      setMessage(editingId ? "Record updated." : "Record created.");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  }

  function edit(row) {
    setEditingId(row.id);
    setForm(Object.fromEntries(config.fields.map((field) => [field, row[field] ?? ""])));
  }

  async function remove(id) {
    if (!window.confirm("Soft-delete this record?")) return;
    try {
      await apiRequest(`/${type}/${id}`, token, { method: "DELETE" });
      setMessage("Record deleted.");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <section className="management-page">
      <div className="section-heading"><div><span>Administration</span><h2>Master data</h2></div></div>
      <div className="tabs">{Object.entries(masterTypes).map(([key, item]) => <button className={type === key ? "active" : ""} key={key} onClick={() => setType(key)}>{item.label}</button>)}</div>
      {message && <p className="inline-message">{message}</p>}
      <form className="crud-form" onSubmit={submit}>
        {config.fields.map((field) => <label key={field}>{field.replaceAll("_", " ")}<input type={field.endsWith("_id") ? "number" : "text"} required={field !== "description"} value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} /></label>)}
        <div className="form-actions"><button type="submit">{editingId ? "Save changes" : `Add ${config.label.slice(0, -1)}`}</button>{editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(emptyFields(config.fields)); }}>Cancel</button>}</div>
      </form>
      <DataTable rows={rows} columns={config.fields} onEdit={edit} onDelete={remove} />
    </section>
  );
}

export function UsersPage({ token }) {
  const [users, setUsers] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [data, roles] = await Promise.all([
        apiRequest("/admin/users?limit=100", token),
        apiRequest("/admin/roles", token),
      ]);
      const roleNames = Object.fromEntries(roles.map((role) => [role.id, role.name]));
      const usersWithRoles = data.map((user) => ({ ...user, role: roleNames[user.role_id] }));
      setUsers(usersWithRoles);
      setDrafts(Object.fromEntries(usersWithRoles.map((user) => [user.id, { role: user.role, employee_id: user.employee_id ?? "" }])));
    } catch (error) { setMessage(error.message); }
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function action(userId, verb) {
    try {
      if (verb === "save") {
        const draft = drafts[userId];
        await apiRequest(`/admin/users/${userId}`, token, { method: "PATCH", body: JSON.stringify({ role: draft.role, employee_id: draft.employee_id === "" ? null : Number(draft.employee_id) }) });
      } else {
        await apiRequest(`/admin/users/${userId}/${verb}`, token, { method: "POST" });
      }
      setMessage(`User ${verb === "save" ? "updated" : `${verb}d`}.`);
      await load();
    } catch (error) { setMessage(error.message); }
  }

  return <section className="management-page"><div className="section-heading"><div><span>Administration</span><h2>Users and approvals</h2></div></div>{message && <p className="inline-message">{message}</p>}<div className="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Employee ID</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><strong>{user.username}</strong><small>#{user.id}</small></td><td><select value={drafts[user.id]?.role ?? user.role} onChange={(e) => setDrafts({ ...drafts, [user.id]: { ...drafts[user.id], role: e.target.value } })}><option>admin</option><option>employee</option><option>query</option></select></td><td><input className="compact-input" type="number" placeholder="Not linked" value={drafts[user.id]?.employee_id ?? ""} onChange={(e) => setDrafts({ ...drafts, [user.id]: { ...drafts[user.id], employee_id: e.target.value } })} /></td><td><em className={`status ${user.approval_status}`}>{user.approval_status}</em></td><td className="row-actions"><button onClick={() => action(user.id, "save")}>Save</button>{user.approval_status !== "approved" && <button onClick={() => action(user.id, "approve")}>Approve</button>}{user.approval_status !== "rejected" && <button className="danger" onClick={() => action(user.id, "reject")}>Reject</button>}</td></tr>)}</tbody></table></div></section>;
}

const employeeFields = ["employee_code", "first_name", "last_name", "date_of_birth", "personal_email", "work_email", "phone_number", "residential_address", "date_of_joining", "employment_type", "employment_status", "division_id", "department_id", "designation_id", "location_id", "office_address_id", "reporting_manager_id"];

export function EmployeesPage({ token, role }) {
  const [rows, setRows] = useState([]);
  const [masterOptions, setMasterOptions] = useState({});
  const [form, setForm] = useState(emptyFields(employeeFields));
  const [editingId, setEditingId] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const employees = await apiRequest("/employees?limit=100", token);
      setRows(employees);
      if (role === "admin") {
        const paths = ["divisions", "departments", "designations", "locations", "office-addresses"];
        const results = await Promise.all(paths.map((path) => apiRequest(`/${path}?limit=100`, token)));
        setMasterOptions({ ...Object.fromEntries(paths.map((path, index) => [path, results[index]])), employees });
      }
    } catch (error) { setMessage(error.message); }
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function edit(row) {
    setEditingId(row.id);
    setForm(Object.fromEntries(employeeFields.map((field) => [field, row[field] ?? ""])));
    setPhoto(row.employee_photo ?? null);
  }

  async function submit(event) {
    event.preventDefault();
    const payload = {};
    for (const [key, value] of Object.entries(form)) {
      if (editingId && value === "") continue;
      payload[key] = key.endsWith("_id") ? (value === "" ? null : Number(value)) : value;
    }
    if (photo) payload.employee_photo = photo;
    try {
      await apiRequest(editingId ? `/employees/${editingId}` : "/employees", token, { method: editingId ? "PATCH" : "POST", body: JSON.stringify(payload) });
      setMessage(editingId ? "Employee updated." : "Employee created.");
      setEditingId(null); setForm(emptyFields(employeeFields)); setPhoto(null); await load();
    } catch (error) { setMessage(error.message); }
  }

  function readPhoto(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPhoto(reader.result);
    reader.readAsDataURL(file);
  }

  async function remove(id) {
    if (!window.confirm("Soft-delete this employee?")) return;
    try { await apiRequest(`/employees/${id}`, token, { method: "DELETE" }); setMessage("Employee deleted."); await load(); } catch (error) { setMessage(error.message); }
  }

  function fieldControl(field) {
    const props = { value: form[field], onChange: (event) => setForm({ ...form, [field]: event.target.value }) };
    if (field === "employment_type") return <select required={!editingId} {...props}><option value="">Select</option><option value="intern">Intern</option><option value="permanent">Permanent</option><option value="contract">Contract</option><option value="temporary">Temporary</option></select>;
    if (field === "employment_status") return <select {...props}><option value="">Select</option><option value="active">Active</option><option value="on_leave">On leave</option><option value="exited">Exited</option></select>;
    const optionPath = { division_id: "divisions", department_id: "departments", designation_id: "designations", location_id: "locations", office_address_id: "office-addresses", reporting_manager_id: "employees" }[field];
    if (optionPath) return <select required={!editingId && field !== "reporting_manager_id"} {...props}><option value="">{field === "reporting_manager_id" ? "No reporting manager" : "Select"}</option>{(masterOptions[optionPath] || []).filter((item) => item.id !== editingId).map((item) => <option key={item.id} value={item.id}>{optionPath === "office-addresses" ? `${item.address_line}, ${item.city}` : optionPath === "employees" ? `${item.employee_code} — ${item.first_name} ${item.last_name}` : `${item.code} — ${item.name}`}</option>)}</select>;
    return <input type={field.includes("date_") ? "date" : field.includes("email") ? "email" : "text"} required={!editingId} {...props} />;
  }

  return <section className="management-page"><div className="section-heading"><div><span>People</span><h2>Employees</h2><p>{role === "query" ? "Read-only results with protected PII removed." : "Create, update and deactivate employee records."}</p></div></div>{message && <p className="inline-message">{message}</p>}{role === "admin" && <form className="crud-form employee-form" onSubmit={submit}>{employeeFields.map((field) => <label key={field}>{field.replaceAll("_", " ")}{fieldControl(field)}</label>)}<label>employee photo<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => readPhoto(e.target.files[0])} /></label><div className="form-actions"><button type="submit">{editingId ? "Save employee" : "Add employee"}</button>{editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(emptyFields(employeeFields)); }}>Cancel</button>}</div></form>}<DataTable rows={rows} columns={["employee_code", "first_name", "last_name", "work_email", "employment_type", "employment_status"]} onEdit={role === "admin" ? edit : null} onDelete={role === "admin" ? remove : null} /></section>;
}

function DataTable({ rows, columns, onEdit, onDelete }) {
  return <div className="table-wrap"><table><thead><tr><th>ID</th>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}{(onEdit || onDelete) && <th>Actions</th>}</tr></thead><tbody>{rows.length === 0 ? <tr><td colSpan={columns.length + 2}>No records found.</td></tr> : rows.map((row) => <tr key={row.id}><td>{row.id}</td>{columns.map((column) => <td key={column}>{row[column] ?? "—"}</td>)}{(onEdit || onDelete) && <td className="row-actions">{onEdit && <button onClick={() => onEdit(row)}>Edit</button>}{onDelete && <button className="danger" onClick={() => onDelete(row.id)}>Delete</button>}</td>}</tr>)}</tbody></table></div>;
}
