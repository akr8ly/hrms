function Sidebar({ role = "employee", collapsed, activeItem, onSelect, onToggle }) {
  const menus = {
    admin: ["Dashboard", "Employees", "Masters", "Users"],
    employee: ["Dashboard", "My Profile"],
    query: ["Dashboard", "Employees"],
  };

  const roleMenus = menus[role] ?? menus.employee;

  return (
    <aside className={collapsed ? "sidebar collapsed" : "sidebar"}>
      <button onClick={onToggle}>{collapsed ? "☰" : "HRMS"}</button>

      {!collapsed && (
        <nav>
          {roleMenus.map((item) => (
            <button
              key={item}
              className={activeItem === item ? "active" : ""}
              onClick={() => onSelect(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      )}
    </aside>
  );
}

export default Sidebar;
