import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ErrorBanner } from '../components/States.jsx';
import { TextField } from '../components/FormField.jsx';
import { useAuth } from '../context/AuthContext.jsx';

export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="brand brand-large">
          <span className="brand-mark" aria-hidden="true">
            ▣
          </span>{' '}
          StockPilot
        </div>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}

export default function Login() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // After signing in, always start from the landing page ('/' -> Dashboard for admins, Orders for staff).
  if (status === 'authed') return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(form.email, form.password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err);
      setSubmitting(false);
    }
  };

  const fieldErrors = error?.fieldErrors || {};
  return (
    <AuthShell title="Sign in" subtitle="Welcome back. Sign in to manage your stock and orders.">
      <form onSubmit={submit} noValidate>
        {error && !Object.keys(fieldErrors).length && <ErrorBanner error={error} />}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          error={fieldErrors.email}
          required
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          error={fieldErrors.password}
          required
        />
        <button className="btn btn-primary btn-block" disabled={submitting || !form.email || !form.password}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="auth-switch">
        New to StockPilot? <Link to="/register">Create an account</Link>
      </p>
    </AuthShell>
  );
}
