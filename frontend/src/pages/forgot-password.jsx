import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../api";


const questionLabels = {
  birthplace: "What is your birthplace?",
  first_school: "What was your first school?",
  childhood_nickname: "What was your childhood nickname?",
};


function ForgotPassword() {
  const [username, setUsername] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function findQuestion(event) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username }),
    });
    const data = await response.json();
    if (!response.ok) {
      setError(data.detail || "Password recovery is unavailable");
      return;
    }
    setQuestion(data.security_question);
  }

  async function resetPassword(event) {
    event.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    const response = await fetch(`${API_BASE_URL}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, security_answer: answer, new_password: password }),
    });
    if (!response.ok) {
      const data = await response.json();
      setError(Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(" · ") : data.detail);
      return;
    }
    navigate("/login", { state: { message: "Password reset successfully. You can now sign in." } });
  }

  return (
    <div className="auth-page">
      <section className="auth-hero">
        <div className="auth-hero-content"><span className="auth-eyebrow">Account recovery</span><h1>Reset your password securely.</h1><p>Answer the verification question created during registration.</p></div>
      </section>
      <section className="auth-form-panel">
        <form className="auth-card" onSubmit={question ? resetPassword : findQuestion}>
          <div className="auth-mark">HR</div><h2>Forgot password</h2>
          {error && <p className="error-message">{error}</p>}
          <label htmlFor="recovery_username">Username</label>
          <input id="recovery_username" value={username} onChange={(event) => setUsername(event.target.value)} disabled={Boolean(question)} required />
          {question && <><label htmlFor="security_answer">{questionLabels[question]}</label><input id="security_answer" value={answer} onChange={(event) => setAnswer(event.target.value)} required /><label htmlFor="new_password">New password</label><input id="new_password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength="7" maxLength="15" pattern="(?=.*[0-9])(?=.*[^A-Za-z0-9]).{7,15}" required /><label htmlFor="confirm_new_password">Confirm new password</label><input id="confirm_new_password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /></>}
          <button type="submit">{question ? "Reset password" : "Continue"}</button>
          <p className="auth-switch"><Link to="/login">Back to sign in</Link></p>
        </form>
      </section>
    </div>
  );
}

export default ForgotPassword;
