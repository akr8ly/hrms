import { useEffect, useState } from "react";

import { apiFetch } from "../api";
import { readPhotoFile } from "../photoUpload";


const createFields = [
  "employee_code", "first_name", "last_name", "date_of_birth", "personal_email",
  "work_email", "phone_number", "residential_address", "date_of_joining",
  "employment_type", "designation_id",
];
const updateFields = createFields.filter((field) => !["employee_code", "designation_id"].includes(field));

const labels = {
  employee_code: "Employee code", first_name: "First name", last_name: "Last name",
  date_of_birth: "Date of birth", personal_email: "Personal email", work_email: "Work email",
  phone_number: "Phone number", residential_address: "Residential address",
  date_of_joining: "Date of joining", employment_type: "Employment type", designation_id: "Designation",
};

function emptyForm() {
  return Object.fromEntries(createFields.map((field) => [field, ""]));
}

async function request(path, options = {}) {
  const response = await apiFetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(", ") : data.detail;
    throw new Error(detail || "Request failed");
  }
  return data;
}

function ActionIcon({ name }) {
  const paths = {
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    delete: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v5M14 11v5" /></>,
  };
  return <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export default function TeamPage() {
  const [team, setTeam] = useState([]);
  const [designations, setDesignations] = useState([]);
  const [form, setForm] = useState(emptyForm());
  const [photo, setPhoto] = useState(null);
  const [photoName, setPhotoName] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [members, roles] = await Promise.all([request("/organization/team"), request("/organization/team/designations")]);
      setTeam(members);
      setDesignations(roles);
      setMessage("");
    } catch (error) {
      setMessage(error.message || "Your team could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function reset() {
    setEditingId(null);
    setForm(emptyForm());
    setPhoto(null);
    setPhotoName("");
  }

  function edit(member) {
    setEditingId(member.id);
    setForm(Object.fromEntries(createFields.map((field) => [field, member[field] ?? ""])));
    setPhoto(member.employee_photo ?? null);
    setPhotoName(member.employee_photo ? "Current photo" : "");
    setMessage("");
  }

  async function choosePhoto(file) {
    if (!file) return;
    try {
      setPhoto(await readPhotoFile(file));
      setPhotoName(file.name);
    } catch (error) {
      setPhoto(null);
      setPhotoName("");
      setMessage(error.message);
    }
  }

  async function submit(event) {
    event.preventDefault();
    const allowedFields = editingId ? updateFields : createFields;
    const payload = Object.fromEntries(allowedFields.map((field) => [
      field,
      field === "designation_id" ? Number(form[field]) : form[field],
    ]));
    if (photo) payload.employee_photo = photo;
    try {
      await request(editingId ? `/organization/team/${editingId}` : "/organization/team", {
        method: editingId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      setMessage(editingId ? "Team member updated." : "Team member added to your team.");
      reset();
      await load();
    } catch (error) {
      setMessage(error.message || "Team member could not be saved.");
    }
  }

  async function remove(member) {
    if (!window.confirm(`Remove ${member.first_name} ${member.last_name} from the HRMS?`)) return;
    try {
      await request(`/organization/team/${member.id}`, { method: "DELETE" });
      setMessage("Team member removed.");
      if (editingId === member.id) reset();
      await load();
    } catch (error) {
      setMessage(error.message || "Team member could not be removed.");
    }
  }

  function control(field) {
    const shared = { value: form[field], onChange: (event) => setForm({ ...form, [field]: event.target.value }) };
    if (field === "employment_type") return <select required {...shared}><option value="">Select</option><option value="intern">Intern</option><option value="permanent">Permanent</option><option value="contract">Contract</option><option value="temporary">Temporary</option></select>;
    if (field === "designation_id") return <select required {...shared}><option value="">Select</option>{designations.map((designation) => <option key={designation.id} value={designation.id}>{designation.code} — {designation.name}</option>)}</select>;
    return <input type={field.includes("date_") ? "date" : field.includes("email") ? "email" : "text"} required {...shared} />;
  }

  const visibleFields = editingId ? updateFields : createFields;
  return <section className="management-page team-page">
    <div className="section-heading"><div><span>People</span><h2>My team</h2><p>Create and maintain your direct reports. Organisation placement, status, and reporting lines remain controlled by HR.</p></div></div>
    {message && <p className="inline-message">{message}</p>}
    <form className="crud-form employee-form" onSubmit={submit}>
      {visibleFields.map((field) => <label key={field}>{labels[field]}{control(field)}</label>)}
      <div className="photo-upload-field"><span>Employee photo</span><label className="file-picker"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { void choosePhoto(event.target.files[0]); }} /><span className="file-picker-button">Choose image</span><span className="file-picker-name">{photoName || "PNG, JPG or WebP"}</span></label></div>
      <div className="form-actions"><button type="submit">{editingId ? "Save team member" : "Add team member"}</button>{editingId && <button type="button" className="secondary" onClick={reset}>Cancel</button>}</div>
    </form>
    <div className="table-wrap data-table-wrap employees-table-wrap"><table className="management-table data-table employees-table"><thead><tr><th>Employee</th><th>Designation</th><th>Work email</th><th>Employment type</th><th>Actions</th></tr></thead><tbody>{loading ? <tr><td colSpan="5">Loading your team…</td></tr> : team.length === 0 ? <tr className="empty-row"><td colSpan="5">No direct reports yet.</td></tr> : team.map((member) => <tr key={member.id}><td><strong>{member.first_name} {member.last_name}</strong><small>{member.employee_code}</small></td><td>{designations.find((item) => item.id === member.designation_id)?.name || "—"}</td><td>{member.work_email}</td><td>{member.employment_type}</td><td><div className="row-actions"><button type="button" className="icon-button" onClick={() => edit(member)}><ActionIcon name="edit" /><span>Edit</span></button><button type="button" className="danger icon-button" onClick={() => { void remove(member); }}><ActionIcon name="delete" /><span>Delete</span></button></div></td></tr>)}</tbody></table></div>
  </section>;
}
