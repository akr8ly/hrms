function NavIcon({ name }) {
  const paths = {
    Dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    Employees: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    Masters: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="2" /><circle cx="16" cy="12" r="2" /><circle cx="10" cy="18" r="2" /></>,
    Users: <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></>,
    Organisation: <><rect x="4" y="3" width="16" height="5" rx="1" /><path d="M12 8v4M6 12h12M6 12v4M18 12v4" /><rect x="2" y="16" width="8" height="5" rx="1" /><rect x="14" y="16" width="8" height="5" rx="1" /></>,
    "My Profile": <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    "My Team": <><circle cx="9" cy="8" r="3" /><path d="M3 21v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 1 1 0 6M18 16a5 5 0 0 1 3 4" /></>,
    Expenses: <><path d="M5 3h14v18H5z" /><path d="M8 7h8M8 11h8M8 15h4" /><path d="m15 16 1.5 1.5L20 14" /></>,
    Queries: <><path d="M21 11.5a8.4 8.4 0 0 1-9 8.5 9.2 9.2 0 0 1-4-.9L3 21l1.9-4.7A8.4 8.4 0 0 1 3 11.5 8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5Z" /><path d="M8 11h.01M12 11h.01M16 11h.01" /></>,
  };

  return <svg className="sidebar-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function PanelIcon({ collapsed }) {
  return <svg className="sidebar-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16M4 12h16M4 19h16" /><path className="panel-arrow" d={collapsed ? "m14 9 3 3-3 3" : "m10 9-3 3 3 3"} /></svg>;
}

function Sidebar({ role = "employee", isReportingManager = false, collapsed, activeItem, onSelect, onToggle }) {
  const menus = {
    admin: ["Dashboard", "Organisation", "Employees", "Expenses", "Queries", "Masters", "Users"],
    employee: ["Dashboard", "Organisation", "My Profile", ...(isReportingManager ? ["My Team"] : []), "Expenses"],
    query: ["Dashboard", "Queries"],
  };

  const roleMenus = menus[role] ?? menus.employee;

  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"}>
      <div className="sidebar-brand"><div className="sidebar-mark">HR</div><div className="sidebar-brand-copy"><strong>HRMS</strong><span>People workspace</span></div></div>
      <button className="sidebar-toggle" type="button" onClick={onToggle} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} title={collapsed ? "Expand navigation" : "Collapse navigation"}><PanelIcon collapsed={collapsed} /><span>{collapsed ? "Expand" : "Collapse"}</span></button>
      <nav aria-label="HRMS navigation">
        {roleMenus.map((item) => (
          <button key={item} type="button" className={activeItem === item ? "active" : ""} onClick={() => onSelect(item)} aria-current={activeItem === item ? "page" : undefined} title={item}>
            <NavIcon name={item} /><span>{item}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-role"><span className="sidebar-role-dot" /><div><small>Signed in as</small><strong>{role}</strong></div></div>
    </aside>
  );
}

export default Sidebar;
