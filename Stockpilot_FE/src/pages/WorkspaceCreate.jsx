import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import { TextField } from '../components/FormField.jsx';
import { ErrorBanner } from '../components/States.jsx';
import { useWorkspaces } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';

export default function WorkspaceCreate() {
  const navigate = useNavigate();
  const toast = useToast();
  const { workspaces, refetch } = useWorkspaces();
  const [name, setName] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    if (!name.trim()) {
      setError({ message: 'Give your workspace a name', fieldErrors: { name: 'Required' }, generalDetails: [] });
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const workspace = await api.workspaces.create(name.trim());
      await refetch();
      toast.success(`Workspace “${workspace.name}” created`);
      navigate(`/w/${workspace.id}/dashboard`, { replace: true });
    } catch (err) {
      setError(err);
      setSubmitting(false);
    }
  };

  return (
    <div className="card center-card">
      <h1>{workspaces.length ? 'New workspace' : 'Create your first workspace'}</h1>
      <p className="muted">
        A workspace holds one business&apos;s products, stock and orders. You&apos;ll be its admin and can add staff later.
      </p>
      <form onSubmit={submit} noValidate>
        {error && !error.fieldErrors?.name && <ErrorBanner error={error} />}
        <TextField label="Workspace name" value={name} onChange={(e) => setName(e.target.value)} error={error?.fieldErrors?.name} maxLength={120} required />
        <button className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Creating…' : 'Create workspace'}
        </button>
      </form>
    </div>
  );
}
