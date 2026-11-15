import { useEffect, useState } from "react";

import { apiFetch } from "../api";


function EmployeeNode({ employee, depth = 0 }) {
  return (
    <li className="org-employee" style={{ "--org-depth": depth }}>
      <div className="org-employee-card">
        <strong>{employee.name}</strong>
        <span>{employee.designation}</span>
        <small>{employee.employee_code}</small>
        {employee.external_reports_to && <small className="org-external-report">Reports to {employee.external_reports_to}</small>}
      </div>
      {employee.direct_reports.length > 0 && (
        <ul className="org-report-list">
          {employee.direct_reports.map((report) => (
            <EmployeeNode key={report.id} employee={report} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}


function DepartmentBranch({ department }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="org-department">
      <button type="button" className="org-branch-button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className="org-chevron" aria-hidden="true">{open ? "−" : "+"}</span>
        <span><strong>{department.name}</strong><small>{department.code} · {department.employee_count} employee{department.employee_count === 1 ? "" : "s"}</small></span>
      </button>
      {open && (department.employees.length > 0 ? (
        <ul className="org-employee-list">
          {department.employees.map((employee) => <EmployeeNode key={employee.id} employee={employee} />)}
        </ul>
      ) : <p className="org-empty">No active employees are assigned to this department.</p>)}
    </section>
  );
}


function DivisionBranch({ division }) {
  const [open, setOpen] = useState(true);
  return (
    <article className="org-division">
      <button type="button" className="org-branch-button org-division-button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className="org-chevron" aria-hidden="true">{open ? "−" : "+"}</span>
        <span><strong>{division.name}</strong><small>{division.code} · {division.employee_count} employee{division.employee_count === 1 ? "" : "s"}</small></span>
      </button>
      {open && (division.departments.length > 0 ? (
        <div className="org-departments">
          {division.departments.map((department) => <DepartmentBranch key={department.id} department={department} />)}
        </div>
      ) : <p className="org-empty">No active departments have employees in this division yet.</p>)}
    </article>
  );
}


export default function OrganisationPage({ canManage = false }) {
  const [tree, setTree] = useState(null);
  const [reportingLines, setReportingLines] = useState([]);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [selectedManagerId, setSelectedManagerId] = useState("");
  const [isManaging, setIsManaging] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadOrganisation() {
      try {
        const treeResponse = await apiFetch("/organization/tree");
        const treeData = await treeResponse.json().catch(() => ({}));
        if (!treeResponse.ok) throw new Error(treeData.detail || "Organisation chart could not be loaded");
        setTree(treeData);
        if (canManage) {
          const reportingLinesResponse = await apiFetch("/organization/reporting-lines");
          const reportingLinesData = await reportingLinesResponse.json().catch(() => ({}));
          if (!reportingLinesResponse.ok) throw new Error(reportingLinesData.detail || "Reporting controls could not be loaded");
          setReportingLines(reportingLinesData);
        }
      } catch (loadError) {
        setError(loadError.message || "Organisation chart could not be loaded");
      }
    }
    void loadOrganisation();
  }, [canManage]);

  const selectedEmployee = reportingLines.find((employee) => employee.id === Number(selectedEmployeeId));

  function selectEmployee(event) {
    const employeeId = event.target.value;
    const employee = reportingLines.find((item) => item.id === Number(employeeId));
    setSelectedEmployeeId(employeeId);
    setSelectedManagerId(employee?.reporting_manager_id ? String(employee.reporting_manager_id) : "");
    setMessage("");
  }

  async function saveReportingLine(event) {
    event.preventDefault();
    if (!selectedEmployee) return;
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(`/organization/reporting-lines/${selectedEmployee.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reporting_manager_id: selectedManagerId === "" ? null : Number(selectedManagerId) }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Reporting line could not be updated");

      const treeResponse = await apiFetch("/organization/tree");
      const treeData = await treeResponse.json().catch(() => ({}));
      if (!treeResponse.ok) throw new Error(treeData.detail || "Organisation chart could not be refreshed");
      setTree(treeData);
      setReportingLines((current) => current.map((employee) => (
        employee.id === data.id ? { ...employee, reporting_manager_id: data.reporting_manager_id } : employee
      )));
      setSelectedManagerId(data.reporting_manager_id ? String(data.reporting_manager_id) : "");
      setMessage("Reporting line saved.");
    } catch (saveError) {
      setError(saveError.message || "Reporting line could not be updated");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="organization-page">
      <div className="section-heading organization-heading">
        <div><span>Organisation</span><h2>Organisation structure</h2><p>Reporting lines are grouped by division and department. Expand a branch to inspect direct reports.</p></div>
        {canManage && <button type="button" className="secondary-button" onClick={() => setIsManaging((value) => !value)} aria-expanded={isManaging}>
          {isManaging ? "Close controls" : "Manage reporting lines"}
        </button>}
      </div>
      {error && <p className="inline-message">{error}</p>}
      {message && <p className="success-message">{message}</p>}
      {canManage && isManaging && <form className="org-controls" onSubmit={saveReportingLine}>
        <div className="org-controls-copy">
          <strong>Reporting lines</strong>
          <p>Choose an employee and assign their direct manager. Clearing the manager makes them a top-level person in their department.</p>
        </div>
        <label>
          Employee
          <select value={selectedEmployeeId} onChange={selectEmployee} required>
            <option value="">Select an employee</option>
            {reportingLines.map((employee) => <option key={employee.id} value={employee.id}>{employee.name} · {employee.employee_code} · {employee.department}</option>)}
          </select>
        </label>
        <label>
          Reports to
          <select value={selectedManagerId} onChange={(event) => setSelectedManagerId(event.target.value)} disabled={!selectedEmployee}>
            <option value="">No reporting manager</option>
            {reportingLines.filter((employee) => employee.id !== selectedEmployee?.id).map((employee) => <option key={employee.id} value={employee.id}>{employee.name} · {employee.designation}</option>)}
          </select>
        </label>
        <button type="submit" className="primary-button" disabled={!selectedEmployee || isSaving}>{isSaving ? "Saving…" : "Save reporting line"}</button>
      </form>}
      {!tree && !error && <p className="org-loading">Loading organisation structure…</p>}
      {tree && <div className="org-tree">
        <div className="org-company"><span>Company</span><strong>{tree.name}</strong></div>
        {tree.divisions.length > 0 ? <div className="org-divisions">{tree.divisions.map((division) => <DivisionBranch key={division.id} division={division} />)}</div> : <p className="org-empty">Create a division and assign employees to begin building the organisation structure.</p>}
      </div>}
    </section>
  );
}
