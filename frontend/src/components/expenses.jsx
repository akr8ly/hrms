import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "../api";
import { readPhotoFile } from "../photoUpload";


const categories = ["travel", "meals", "accommodation", "local_transport", "supplies", "other"];
const costCenters = [
  { value: "CORP-ADMIN", label: "CORP-ADMIN — Corporate Administration" },
  { value: "FIN-OPS", label: "FIN-OPS — Finance Operations" },
  { value: "HR-OPS", label: "HR-OPS — Human Resources" },
  { value: "SALES-OPS", label: "SALES-OPS — Sales Operations" },
  { value: "TECH-OPS", label: "TECH-OPS — Technology Operations" },
];

function blankEntry() {
  return { expense_date: new Date().toISOString().slice(0, 10), category: "travel", description: "", requested_amount: "", receipt_image: null, receipt_name: "" };
}

async function request(path, options = {}) {
  const response = await apiFetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function Status({ value }) {
  return <span className={`expense-status expense-${value}`}>{value.replaceAll("_", " ")}</span>;
}

function ActionIcon({ name }) {
  const paths = {
    edit: <><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></>,
    delete: <><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v5M14 11v5" /></>,
    submit: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    approve: <path d="m5 12 4 4L19 6" />,
    reject: <><path d="m6 6 12 12M18 6 6 18" /></>,
    reimburse: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 10h10M7 14h5" /><path d="m16 3 2 2-2 2" /></>,
  };
  return <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function IconAction({ icon, label, danger = false, onClick }) {
  return <button type="button" className={`icon-button expense-action-icon${danger ? " danger" : ""}`} aria-label={label} title={label} onClick={onClick}><ActionIcon name={icon} /><span>{label}</span></button>;
}

function claimEntriesPayload(entries) {
  return entries.map(({ expense_date, category, description, requested_amount, receipt_image }) => ({
    expense_date,
    category,
    description,
    requested_amount,
    receipt_image,
  }));
}

export default function ExpensesPage({ user }) {
  const [claims, setClaims] = useState([]);
  const [costCenter, setCostCenter] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [entries, setEntries] = useState([blankEntry()]);
  const [editingId, setEditingId] = useState(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const total = useMemo(() => entries.reduce((sum, entry) => sum + (Number(entry.requested_amount) || 0), 0), [entries]);

  async function load() {
    try {
      setClaims(await request("/expenses/claims"));
      setMessage("");
    } catch (error) {
      setMessage(error.message || "Expense claims could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function changeEntry(index, field, value) {
    setEntries((current) => current.map((entry, itemIndex) => itemIndex === index ? { ...entry, [field]: value } : entry));
  }

  async function chooseReceipt(index, file) {
    if (!file) return;
    try {
      const image = await readPhotoFile(file);
      setEntries((current) => current.map((entry, itemIndex) => itemIndex === index ? { ...entry, receipt_image: image, receipt_name: file.name } : entry));
    } catch (error) { setMessage(error.message || "Receipt image could not be read."); }
  }

  function resetForm() {
    setEditingId(null); setCostCenter(""); setCurrency("INR"); setEntries([blankEntry()]);
  }

  function editClaim(claim) {
    setEditingId(claim.id);
    setCostCenter(claim.cost_center);
    setCurrency(claim.currency);
    setEntries(claim.entries.map((entry) => ({ ...entry, receipt_name: entry.receipt_image ? "Receipt attached" : "" })));
    setMessage("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function createClaim(event) {
    event.preventDefault();
    try {
      const claim = await request(editingId ? `/expenses/claims/${editingId}` : "/expenses/claims", { method: editingId ? "PATCH" : "POST", body: JSON.stringify({ cost_center: costCenter, currency, entries: claimEntriesPayload(entries) }) });
      setClaims((current) => editingId ? current.map((item) => item.id === claim.id ? claim : item) : [claim, ...current]);
      resetForm();
      setMessage(editingId ? "Draft claim updated." : "Expense claim saved as a draft.");
    } catch (error) { setMessage(error.message || "Expense claim could not be saved."); }
  }

  async function deleteDraft(claim) {
    if (!window.confirm(`Delete draft claim #${claim.id}?`)) return;
    try {
      await request(`/expenses/claims/${claim.id}`, { method: "DELETE" });
      setClaims((current) => current.filter((item) => item.id !== claim.id));
      if (editingId === claim.id) resetForm();
      setMessage("Draft claim deleted.");
    } catch (error) { setMessage(error.message || "Draft claim could not be deleted."); }
  }

  async function action(claim, endpoint, body) {
    try {
      const updated = await request(`/expenses/claims/${claim.id}${endpoint}`, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      setClaims((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(`Claim ${updated.status.replaceAll("_", " ")}.`);
    } catch (error) { setMessage(error.message || "Claim action could not be completed."); }
  }

  function decide(claim, level, approval) {
    const remarks = approval ? "" : window.prompt("Reason for rejection:");
    if (remarks === null) return;
    void action(claim, level === 1 ? "/l1-decision" : "/l2-decision", { action: approval ? "approved" : "rejected", remarks: remarks || null });
  }

  const canCreate = user.role === "employee";
  return <section className="management-page expense-page">
    <div className="section-heading"><div><span>Finance</span><h2>Expense reimbursements</h2><p>Submit up to five cost entries per claim. Claims move through L1 manager review, then L2 finance approval.</p></div></div>
    {message && <p className="inline-message">{message}</p>}
    {canCreate && <form className="expense-form" onSubmit={createClaim}>
      <div className="expense-form-header"><strong>{editingId ? `Editing draft #${editingId}` : "New claim"}</strong><span>Requested total: {currency} {total.toFixed(2)}</span></div>
      <div className="expense-claim-fields"><label>Cost centre<select required value={costCenter} onChange={(event) => setCostCenter(event.target.value)}><option value="" disabled>Select a cost centre</option>{costCenters.map((costCenterOption) => <option key={costCenterOption.value} value={costCenterOption.value}>{costCenterOption.label}</option>)}</select></label><label>Currency<input required minLength="3" maxLength="3" value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label></div>
      {entries.map((entry, index) => <div className="expense-entry" key={index}><strong>Entry {index + 1}</strong><label>Date<input type="date" required value={entry.expense_date} onChange={(event) => changeEntry(index, "expense_date", event.target.value)} /></label><label>Category<select value={entry.category} onChange={(event) => changeEntry(index, "category", event.target.value)}>{categories.map((category) => <option key={category} value={category}>{category.replaceAll("_", " ")}</option>)}</select></label><label>Description<input required minLength="3" maxLength="300" value={entry.description} onChange={(event) => changeEntry(index, "description", event.target.value)} /></label><label>Amount<input required type="number" min="0.01" step="0.01" value={entry.requested_amount} onChange={(event) => changeEntry(index, "requested_amount", event.target.value)} /></label><div className="expense-receipt"><span>Receipt (optional)</span><label className="file-picker"><input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { void chooseReceipt(index, event.target.files[0]); }} /><span className="file-picker-button">Attach image</span><span className="file-picker-name">{entry.receipt_name || "PNG, JPG or WebP"}</span></label></div>{entries.length > 1 && <button type="button" className="secondary" onClick={() => setEntries((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>}</div>)}
      <div className="form-actions">{entries.length < 5 && <button type="button" className="secondary" onClick={() => setEntries((current) => [...current, blankEntry()])}>Add entry ({entries.length}/5)</button>}<button type="submit">{editingId ? "Save changes" : "Save draft"}</button>{editingId && <button type="button" className="secondary" onClick={resetForm}>Cancel edit</button>}</div>
    </form>}
    <div className="table-wrap data-table-wrap expenses-table-wrap"><table className="management-table data-table expenses-table"><thead><tr><th>Claim</th><th>Cost centre</th><th>Requested</th><th>Status</th><th>Approvals</th><th>Actions</th></tr></thead><tbody>{loading ? <tr><td colSpan="6">Loading claims…</td></tr> : claims.length === 0 ? <tr className="empty-row"><td colSpan="6">No expense claims yet.</td></tr> : claims.map((claim) => { const mine = claim.claimant_employee_id === user.employee_id; const editable = mine && claim.status === "draft"; const l1 = user.role === "employee" && !mine && claim.status === "submitted"; const l2 = user.role === "admin" && claim.status === "l1_approved"; return <tr key={claim.id}><td><strong>{claim.id}</strong></td><td>{claim.cost_center}</td><td>{claim.currency} {Number(claim.requested_total).toFixed(2)}</td><td><Status value={claim.status} /></td><td>L1: {claim.l1_approved_total ?? "—"}<br />L2: {claim.l2_approved_total ?? "—"}</td><td><div className="row-actions">{editable && <><IconAction icon="edit" label="Edit draft" onClick={() => editClaim(claim)} /><IconAction icon="delete" label="Delete draft" danger onClick={() => { void deleteDraft(claim); }} /><IconAction icon="submit" label="Submit claim" onClick={() => { void action(claim, "/submit"); }} /></>}{l1 && <><IconAction icon="approve" label="L1 approve" onClick={() => decide(claim, 1, true)} /><IconAction icon="reject" label="L1 reject" danger onClick={() => decide(claim, 1, false)} /></>}{l2 && <><IconAction icon="approve" label="L2 approve" onClick={() => decide(claim, 2, true)} /><IconAction icon="reject" label="L2 reject" danger onClick={() => decide(claim, 2, false)} /></>}{user.role === "admin" && claim.status === "l2_approved" && <IconAction icon="reimburse" label="Mark reimbursed" onClick={() => { void action(claim, "/reimburse"); }} />}</div></td></tr>; })}</tbody></table></div>
  </section>;
}
