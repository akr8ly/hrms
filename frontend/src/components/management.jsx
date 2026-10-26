import { useEffect, useState } from "react";
import { apiFetch } from "../api";

function ActionIcon({ name }) {
  const paths = {
    save: <><path d="M5 3h12l2 2v16H5z" /><path d="M8 3v6h8V3M8 21v-8h8v8" /></>,
    approve: <><path d="m5 12 4 4L19 6" /></>,
    reject: <><path d="M18 6 6 18M6 6l12 12" /></>,
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    delete: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v5M14 11v5" /></>,
  };
  return <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

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

async function apiRequest(path, _token, options = {}) {
  const response = await apiFetch(path, {
    ...options,
    headers: {
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
    void load();
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
  const pageSize = 25;
  const [users, setUsers] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [message, setMessage] = useState("");
  const [page, setPage] = useState(0);
  const [hasNextPage, setHasNextPage] = useState(false);

  async function load() {
    try {
      const [data, roles] = await Promise.all([
        apiRequest(`/admin/users?limit=${pageSize}&offset=${page * pageSize}`, token),
        apiRequest("/admin/roles", token),
      ]);
      const roleNames = Object.fromEntries(roles.map((role) => [role.id, role.name]));
      const usersWithRoles = data.map((user) => ({ ...user, role: roleNames[user.role_id] }));
      setUsers(usersWithRoles);
      setHasNextPage(data.length === pageSize);
      setDrafts(Object.fromEntries(usersWithRoles.map((user) => [user.id, { role: user.role, employee_id: user.employee_id ?? "" }])));
    } catch (error) { setMessage(error.message); }
  }
  useEffect(() => { void load(); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

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

  return <section className="management-page"><div className="section-heading approval-heading"><div><span>Administration</span><h2>Users and approvals</h2><p>Review registrations, assign roles and link employee records.</p></div><div className="record-count"><strong>{users.length}</strong><span>on this page</span></div></div>{message && <p className="inline-message">{message}</p>}<div className="approval-scroll-note" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M3 12h18M16 7l5 5-5 5" /></svg><span>Scroll sideways to view every column</span></div><div className="table-wrap approval-table-wrap"><table className="management-table approval-table"><thead><tr><th>User</th><th>Role</th><th>Employee ID</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td data-label="User"><strong>{user.username}</strong><small>#{user.id}</small></td><td data-label="Role"><select aria-label={`Role for ${user.username}`} value={drafts[user.id]?.role ?? user.role} onChange={(e) => setDrafts({ ...drafts, [user.id]: { ...drafts[user.id], role: e.target.value } })}><option>admin</option><option>employee</option><option>query</option></select></td><td data-label="Employee ID"><input aria-label={`Employee ID for ${user.username}`} className="compact-input" type="number" placeholder="Not linked" value={drafts[user.id]?.employee_id ?? ""} onChange={(e) => setDrafts({ ...drafts, [user.id]: { ...drafts[user.id], employee_id: e.target.value } })} /></td><td data-label="Status"><em className={`status status-pill ${user.approval_status}`}>{user.approval_status}</em></td><td data-label="Actions"><div className="row-actions"><button title={`Save ${user.username}`} aria-label={`Save ${user.username}`} className="icon-button" onClick={() => { void action(user.id, "save"); }}><ActionIcon name="save" /><span>Save</span></button>{user.approval_status !== "approved" && <button title={`Approve ${user.username}`} aria-label={`Approve ${user.username}`} className="icon-button" onClick={() => { void action(user.id, "approve"); }}><ActionIcon name="approve" /><span>Approve</span></button>}{user.approval_status !== "rejected" && <button title={`Reject ${user.username}`} aria-label={`Reject ${user.username}`} className="danger icon-button" onClick={() => { void action(user.id, "reject"); }}><ActionIcon name="reject" /><span>Reject</span></button>}</div></td></tr>)}</tbody></table></div><div className="table-pagination"><span>Page {page + 1} · {pageSize} users maximum</span><div><button type="button" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous</button><button type="button" disabled={!hasNextPage} onClick={() => setPage((value) => value + 1)}>Next</button></div></div></section>;
}

const employeeFields = ["employee_code", "first_name", "last_name", "date_of_birth", "personal_email", "work_email", "phone_number", "residential_address", "date_of_joining", "employment_type", "employment_status", "division_id", "department_id", "designation_id", "location_id", "office_address_id", "reporting_manager_id"];

export function EmployeesPage({ token, role }) {
  const [rows, setRows] = useState([]);
  const [masterOptions, setMasterOptions] = useState({});
  const [form, setForm] = useState(emptyFields(employeeFields));
  const [editingId, setEditingId] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [photoName, setPhotoName] = useState("");
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
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function edit(row) {
    setEditingId(row.id);
    setForm(Object.fromEntries(employeeFields.map((field) => [field, row[field] ?? ""])));
    setPhoto(row.employee_photo ?? null);
    setPhotoName(row.employee_photo ? "Current photo" : "");
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
      setEditingId(null); setForm(emptyFields(employeeFields)); setPhoto(null); setPhotoName(""); await load();
    } catch (error) { setMessage(error.message); }
  }

  function readPhoto(file) {
    if (!file) return;
    setPhotoName(file.name);
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

  return <section className="management-page"><div className="section-heading"><div><span>People</span><h2>Employees</h2><p>{role === "query" ? "Read-only results with protected PII removed." : "Create, update and deactivate employee records."}</p></div></div>{message && <p className="inline-message">{message}</p>}{role === "admin" && <form className="crud-form employee-form" onSubmit={submit}>{employeeFields.map((field) => <label key={field}>{field.replaceAll("_", " ")}{fieldControl(field)}</label>)}<div className="photo-upload-field"><span>Employee photo</span><label className="file-picker"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => readPhoto(e.target.files[0])} /><span className="file-picker-button"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 16.5V19a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2.5M8 9l4-4 4 4M12 5v11" /></svg>Choose image</span><span className="file-picker-name">{photoName || "PNG, JPG or WebP"}</span></label></div><div className="form-actions"><button type="submit">{editingId ? "Save employee" : "Add employee"}</button>{editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm(emptyFields(employeeFields)); setPhoto(null); setPhotoName(""); }}>Cancel</button>}</div></form>}<DataTable variant="employees" rows={rows} columns={["employee_code", "first_name", "last_name", "work_email", "employment_type", "employment_status"]} onEdit={role === "admin" ? edit : null} onDelete={role === "admin" ? remove : null} /></section>;
}

function DataTable({ rows, columns, onEdit, onDelete, variant = "masters" }) {
  return <><div className="table-scroll-note" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m8 7-5 5 5 5M3 12h18M16 7l5 5-5 5" /></svg><span>Scroll sideways to view every column</span></div><div className={`table-wrap data-table-wrap ${variant}-table-wrap`}><table className={`management-table data-table ${variant}-table`}><thead><tr><th>ID</th>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}{(onEdit || onDelete) && <th>Actions</th>}</tr></thead><tbody>{rows.length === 0 ? <tr className="empty-row"><td colSpan={columns.length + 2}>No records found.</td></tr> : rows.map((row) => <tr key={row.id}><td>{row.id}</td>{columns.map((column) => <td key={column}>{row[column] ?? "—"}</td>)}{(onEdit || onDelete) && <td><div className="row-actions">{onEdit && <button title="Edit" aria-label={`Edit record ${row.id}`} className="icon-button" onClick={() => onEdit(row)}><ActionIcon name="edit" /><span>Edit</span></button>}{onDelete && <button title="Delete" aria-label={`Delete record ${row.id}`} className="danger icon-button" onClick={() => { void onDelete(row.id); }}><ActionIcon name="delete" /><span>Delete</span></button>}</div></td>}</tr>)}</tbody></table></div></>;
}
