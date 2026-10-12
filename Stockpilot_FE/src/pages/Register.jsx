import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ErrorBanner } from '../components/States.jsx';
import { TextField } from '../components/FormField.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { AuthShell } from './Login.jsx';

export default function Register() {
  const { status, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', password: '', workspace_name: '' });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === 'authed') return <Navigate to="/" replace />;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const validate = () => {
    const next = {};
    if (!form.full_name.trim()) next.full_name = 'Your name is required';
    if (!/^\S+@\S+\.\S+$/.test(form.email)) next.email = 'Enter a valid email address';
    if (form.password.length < 8) next.password = 'Use at least 8 characters';
    return next;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    const clientErrors = validate();
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) return;
    setSubmitting(true);
    setError(null);
    try {
      await register({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        workspace_name: form.workspace_name.trim() || undefined,
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err);
      setErrors(err.fieldErrors || {});
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Create your account" subtitle="Set up a workspace for your business in a minute.">
      <form onSubmit={submit} noValidate>
        {error && !Object.keys(errors).length && <ErrorBanner error={error} />}
        <TextField label="Your name" autoComplete="name" value={form.full_name} onChange={set('full_name')} error={errors.full_name} required />
        <TextField label="Email" type="email" autoComplete="email" value={form.email} onChange={set('email')} error={errors.email} required />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={set('password')}
          error={errors.password}
          hint="At least 8 characters."
          required
        />
        <TextField
          label="Business / workspace name"
          value={form.workspace_name}
          onChange={set('workspace_name')}
          error={errors.workspace_name}
          hint="Optional. Leave it empty if an admin will add you to their workspace as staff."
        />
        <button className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
