import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../api";

function Login() {
  const [form, setForm] = useState({
    username: "",
    password: "",
  });

  const [error, setError] = useState("");
  const navigate = useNavigate();

  function handleChange(event) {
    setForm({
      ...form,
      [event.target.name]: event.target.value,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/auth/login`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(form),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || "Login failed");
        return;
      }

      localStorage.setItem("access_token", data.access_token);
      navigate("/dashboard");
    } catch {
      setError("Cannot connect to the HRMS API");
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <div className="auth-hero-content">
          <span className="auth-eyebrow">Human Resource Management</span>
          <h1>One place for your people and workplace.</h1>
          <p>
            Manage employee records, organisation masters and secure HR data
            through one simple workspace.
          </p>
        </div>
        <p className="auth-footer">Secure HRMS · FastAPI + React</p>
      </section>

      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-mark">HR</div>
          <span className="auth-kicker">Welcome back</span>
          <h2>Sign in to HRMS</h2>
          <p className="auth-subtitle">Enter your account details to continue.</p>

          {error && <p className="error-message">{error}</p>}

          <label htmlFor="username">Username</label>
          <input
            id="username"
            name="username"
            value={form.username}
            onChange={handleChange}
            placeholder="Enter your username"
            autoComplete="username"
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            value={form.password}
            onChange={handleChange}
            placeholder="Enter your password"
            autoComplete="current-password"
            required
          />

          <button type="submit">Sign in</button>

          <p className="auth-switch">
            New employee? <Link to="/register">Create an account</Link>
          </p>
        </form>
      </section>
    </div>
  );
}

export default Login;
