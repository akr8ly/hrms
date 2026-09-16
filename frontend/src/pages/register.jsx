import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../api";

function Register() {
  const [form, setForm] = useState({
    username: "",
    password: "",
    role: "employee",
  });

  const [employee, setEmployee] = useState({
    employee_code: "",
    first_name: "",
    last_name: "",
    date_of_birth: "",
    personal_email: "",
    work_email: "",
    phone_number: "",
    residential_address: "",
    date_of_joining: "",
    employment_type: "intern",
    employment_status: "active",
    division_id: "",
    department_id: "",
    designation_id: "",
    location_id: "",
    office_address_id: "",
    reporting_manager_id: "",
  });

  const [options, setOptions] = useState({
    divisions: [],
    departments: [],
    designations: [],
    locations: [],
    office_addresses: [],
  });

  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    async function loadOptions() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/auth/registration-options`
        );
        if (!response.ok) {
          setError("Registration options could not be loaded");
          return;
        }
        setOptions(await response.json());
      } catch {
        setError("Cannot connect to the HRMS API");
      }
    }

    loadOptions();
  }, []);

  function handleChange(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  function handleEmployeeChange(event) {
    const { name, value } = event.target;
    setEmployee((current) => ({
      ...current,
      [name]: value,
      ...(name === "location_id" ? { office_address_id: "" } : {}),
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (form.password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    try {
      const employeePayload = {
        ...employee,
        division_id: Number(employee.division_id),
        department_id: Number(employee.department_id),
        designation_id: Number(employee.designation_id),
        location_id: Number(employee.location_id),
        office_address_id: Number(employee.office_address_id),
        reporting_manager_id: employee.reporting_manager_id
          ? Number(employee.reporting_manager_id)
          : null,
      };

      const response = await fetch(
        `${API_BASE_URL}/auth/register`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username: form.username,
            password: form.password,
            role: form.role,
            employee: form.role === "employee" ? employeePayload : null,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const message = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join(" · ")
          : data.detail;
        setError(message || "Registration failed");
        return;
      }

      navigate("/login");
    } catch {
      setError("Cannot connect to the HRMS API");
    }
  }

  return (
    <div className="auth-page register-page">
      <section className="auth-hero">
        <div className="auth-hero-content">
          <span className="auth-eyebrow">Employee self-service</span>
          <h1>Start your journey with a secure HR account.</h1>
          <p>
            Create a secure Employee profile or a read-only Query account from
            one guided registration form.
          </p>
        </div>
        <p className="auth-footer">Secure HRMS · FastAPI + React</p>
      </section>

      <section className="auth-form-panel register-panel">
        <form className="auth-card register-card" onSubmit={handleSubmit}>
          <div className="auth-mark">HR</div>
          <span className="auth-kicker">Get started</span>
          <h2>Create your account</h2>
          <p className="auth-subtitle">
            Select your role and complete the required account information.
          </p>

          {error && <p className="error-message">{error}</p>}

          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            value={form.username}
            onChange={handleChange}
            placeholder="Choose a username"
            autoComplete="username"
            minLength="3"
            maxLength="50"
            required
          />

          <label htmlFor="role">Role</label>
          <select
            id="role"
            name="role"
            value={form.role}
            onChange={handleChange}
            required
          >
            <option value="employee">Employee</option>
            <option value="query">Query</option>
          </select>

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            placeholder="Create a password"
            autoComplete="new-password"
            minLength="15"
            required
          />

          <label htmlFor="confirmPassword">Confirm password</label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Repeat your password"
            autoComplete="new-password"
            minLength="15"
            required
          />

          {form.role === "employee" && (
            <fieldset className="employee-fields">
              <legend>Employee profile</legend>

              <div className="form-grid">
                <div>
                  <label htmlFor="employee_code">Employee code</label>
                  <input id="employee_code" name="employee_code" value={employee.employee_code} onChange={handleEmployeeChange} pattern="[A-Za-z0-9]+" required />
                </div>
                <div>
                  <label htmlFor="employment_type">Employment type</label>
                  <select id="employment_type" name="employment_type" value={employee.employment_type} onChange={handleEmployeeChange} required>
                    <option value="intern">Intern</option>
                    <option value="permanent">Permanent</option>
                    <option value="contract">Contract</option>
                    <option value="temporary">Temporary</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="first_name">First name</label>
                  <input id="first_name" name="first_name" value={employee.first_name} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="last_name">Last name</label>
                  <input id="last_name" name="last_name" value={employee.last_name} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="date_of_birth">Date of birth</label>
                  <input id="date_of_birth" name="date_of_birth" type="date" value={employee.date_of_birth} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="date_of_joining">Date of joining</label>
                  <input id="date_of_joining" name="date_of_joining" type="date" value={employee.date_of_joining} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="personal_email">Personal email</label>
                  <input id="personal_email" name="personal_email" type="email" value={employee.personal_email} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="work_email">Work email</label>
                  <input id="work_email" name="work_email" type="email" value={employee.work_email} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="phone_number">Phone number</label>
                  <input id="phone_number" name="phone_number" value={employee.phone_number} onChange={handleEmployeeChange} minLength="8" maxLength="20" required />
                </div>
                <div>
                  <label htmlFor="employment_status">Employment status</label>
                  <select id="employment_status" name="employment_status" value={employee.employment_status} onChange={handleEmployeeChange} required>
                    <option value="active">Active</option>
                    <option value="on_leave">On leave</option>
                    <option value="exited">Exited</option>
                  </select>
                </div>
                <div className="full-width">
                  <label htmlFor="residential_address">Residential address</label>
                  <input id="residential_address" name="residential_address" value={employee.residential_address} onChange={handleEmployeeChange} required />
                </div>
                <div>
                  <label htmlFor="division_id">Division</label>
                  <select id="division_id" name="division_id" value={employee.division_id} onChange={handleEmployeeChange} required>
                    <option value="">Select division</option>
                    {options.divisions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="department_id">Department</label>
                  <select id="department_id" name="department_id" value={employee.department_id} onChange={handleEmployeeChange} required>
                    <option value="">Select department</option>
                    {options.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="designation_id">Designation</label>
                  <select id="designation_id" name="designation_id" value={employee.designation_id} onChange={handleEmployeeChange} required>
                    <option value="">Select designation</option>
                    {options.designations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="location_id">Location</label>
                  <select id="location_id" name="location_id" value={employee.location_id} onChange={handleEmployeeChange} required>
                    <option value="">Select location</option>
                    {options.locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="office_address_id">Office address</label>
                  <select id="office_address_id" name="office_address_id" value={employee.office_address_id} onChange={handleEmployeeChange} required>
                    <option value="">Select office address</option>
                    {options.office_addresses
                      .filter((item) => String(item.location_id) === String(employee.location_id))
                      .map((item) => <option key={item.id} value={item.id}>{item.address_line}, {item.city}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="reporting_manager_id">Reporting manager ID (optional)</label>
                  <input id="reporting_manager_id" name="reporting_manager_id" type="number" min="1" value={employee.reporting_manager_id} onChange={handleEmployeeChange} />
                </div>
              </div>
            </fieldset>
          )}

          <button type="submit">Create account</button>

          <p className="auth-switch">
            Already registered? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </section>
    </div>
  );
}

export default Register;
