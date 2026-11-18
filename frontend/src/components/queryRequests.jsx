import { Fragment, useCallback, useEffect, useState } from "react";

import { apiFetch } from "../api";


const queryTypes = [
  { value: "employee_related", label: "Employee related", description: "Ask about an employee record, reporting line, or HR information." },
  { value: "application_usage", label: "Application usage", description: "Report an HRMS screen, workflow, or access issue." },
  { value: "reimbursement_report", label: "Reimbursement report", description: "Ask about an expense claim, approval, or reimbursement status." },
  { value: "llm_calls", label: "HR assistant / LLM", description: "Report an incorrect, unsafe, or unexpected HR-assistant response." },
];

function emptyForm() {
  return { category: "employee_related", subject: "", description: "", related_reference: "", expense_claim_id: "" };
}

function labelForCategory(category) {
  return queryTypes.find((item) => item.value === category)?.label || category;
}

function Status({ value }) {
  return <span className={`query-status query-${value}`}>{value.replaceAll("_", " ")}</span>;
}

function dateLabel(value) {
  return new Date(value).toLocaleDateString();
}

function timeLabel(value) {
  return new Date(value).toLocaleTimeString();
}

function MailReference({ value }) {
  if (!value) return <span className="query-reference-empty">—</span>;
  return <span className="query-reference"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>{value}</span>;
}

function DownloadIcon() {
  return <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 20h14" /></svg>;
}

function ViewIcon() {
  return <svg className="button-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></svg>;
}

export default function QueryRequestsPage({ adminMode = false }) {
  const [form, setForm] = useState(emptyForm());
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [expandedRequestId, setExpandedRequestId] = useState(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(async (nextOffset = 0) => {
    try {
      const path = adminMode ? "/queries/admin/requests" : "/queries/requests";
      const response = await apiFetch(`${path}?limit=20&offset=${nextOffset}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Your queries could not be loaded");
      setRequests((current) => nextOffset === 0 ? data : [...current, ...data]);
      setOffset(nextOffset + data.length);
      setHasMore(data.length === 20);
    } catch (error) {
      setMessage(error.message || "Your queries could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [adminMode]);

  useEffect(() => { void load(); }, [load]);

  async function downloadQueryReport(queryId) {
    setMessage("");
    try {
      const response = await apiFetch(`/queries/admin/requests/${queryId}/report.pdf`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Query PDF could not be downloaded");
      }
      const file = URL.createObjectURL(await response.blob());
      const download = document.createElement("a");
      download.href = file;
      download.download = `hrms-query-${queryId}.pdf`;
      download.click();
      URL.revokeObjectURL(file);
    } catch (error) {
      setMessage(error.message || "Query PDF could not be downloaded.");
    }
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const payload = {
        ...form,
        expense_claim_id: form.expense_claim_id ? Number(form.expense_claim_id) : null,
      };
      const response = await apiFetch("/queries/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Query could not be submitted");
      setRequests((current) => [data, ...current]);
      setForm(emptyForm());
      setMessage("Your query was submitted for review.");
    } catch (error) {
      setMessage(error.message || "Query could not be submitted.");
    } finally {
      setSaving(false);
    }
  }

  const selectedType = queryTypes.find((item) => item.value === form.category);
  return <section className="management-page query-requests-page">
    <div className="section-heading query-page-heading"><div><span>{adminMode ? "Administration" : "Support"}</span><h2>{adminMode ? "Query review" : "Queries"}</h2><p>{adminMode ? "Read submitted requests and download an immutable PDF report." : "Submit a structured request and track only the queries you created."}</p></div></div>
    {message && <p className="inline-message">{message}</p>}
    {!adminMode && <form className="query-request-form" onSubmit={submit}>
      <div className="query-form-heading"><div><strong>New query</strong><small>{selectedType?.description}</small></div></div>
      <label>Query type<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{queryTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
      <label>Subject<input required minLength="4" maxLength="120" value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} placeholder="Briefly describe what you need" /></label>
      <label>Related reference <span>(optional)</span><input maxLength="100" value={form.related_reference} onChange={(event) => setForm({ ...form, related_reference: event.target.value })} placeholder="Employee code, claim number, or approximate time" /></label>
      {form.category === "reimbursement_report" && <label>Expense claim ID <span>(optional)</span><input type="number" min="1" value={form.expense_claim_id} onChange={(event) => setForm({ ...form, expense_claim_id: event.target.value })} placeholder="Link a claim for status tracking" /></label>}
      <label className="query-description">Details<textarea required minLength="10" maxLength="2000" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Include only the information needed to investigate this query." /></label>
      <div className="form-actions"><button type="submit" disabled={saving}>{saving ? "Submitting…" : "Submit query"}</button></div>
    </form>}
    {adminMode ? <div className="table-wrap data-table-wrap query-review-table-wrap"><table className="management-table data-table query-review-table"><thead><tr><th>Sender</th><th>Query type</th><th>Subject</th><th>Reference</th><th>Submitted</th><th>Status</th><th aria-label="Actions" /></tr></thead><tbody>{loading ? <tr><td colSpan="7">Loading submitted queries…</td></tr> : requests.length === 0 ? <tr className="empty-row"><td colSpan="7">No submitted non-expense queries are available.</td></tr> : requests.map((request) => <Fragment key={request.id}><tr><td>{request.sender}</td><td>{labelForCategory(request.category)}</td><td>{request.subject}</td><td><MailReference value={request.related_reference} /></td><td><span>{dateLabel(request.created_at)}</span><small>{timeLabel(request.created_at)}</small></td><td><Status value={request.status} /></td><td className="query-actions-cell"><div className="query-row-actions"><button type="button" className="query-report-download" aria-label={`${expandedRequestId === request.id ? "Hide" : "View"} details for ${request.subject}`} title={expandedRequestId === request.id ? "Hide details" : "View details"} aria-expanded={expandedRequestId === request.id} onClick={() => setExpandedRequestId((current) => current === request.id ? null : request.id)}><ViewIcon /></button><button type="button" className="query-report-download" aria-label={`Download PDF for ${request.subject}`} title="Download PDF" onClick={() => { void downloadQueryReport(request.id); }}><DownloadIcon /></button></div></td></tr>{expandedRequestId === request.id && <tr className="query-details-row"><td colSpan="7"><div><span>Details</span><p>{request.description}</p></div></td></tr>}</Fragment>)}</tbody></table></div> : <div className="table-wrap data-table-wrap query-requests-table-wrap"><table className="management-table data-table query-requests-table"><thead><tr><th>Type</th><th>Subject</th><th>Reference</th><th>Status</th><th>Submitted</th></tr></thead><tbody>{loading ? <tr><td colSpan="5">Loading your queries…</td></tr> : requests.length === 0 ? <tr className="empty-row"><td colSpan="5">You have not submitted any queries yet.</td></tr> : requests.map((request) => <tr key={request.id}><td>{labelForCategory(request.category)}</td><td><strong>{request.subject}</strong><small>{request.description}</small></td><td>{request.related_reference || "—"}</td><td><Status value={request.status} /></td><td>{dateLabel(request.created_at)}</td></tr>)}</tbody></table></div>}
    {hasMore && <div className="load-more-wrap"><button type="button" className="secondary-button" onClick={() => { void load(offset); }}>Load more</button></div>}
  </section>;
}
