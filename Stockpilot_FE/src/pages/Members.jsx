import { useState } from 'react';
import { api } from '../api/client.js';
import { RoleBadge } from '../components/Badges.jsx';
import { SelectField, TextField } from '../components/FormField.jsx';
import { EmptyState, ErrorBanner, Loading } from '../components/States.jsx';
import { useConfirm } from '../context/ConfirmContext.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useApi } from '../hooks/useApi.js';
import { formatDate } from '../utils/format.js';

export default function Members() {
  const { workspaceId, workspace } = useCurrentWorkspace();
  const { user } = useAuth();
  const confirm = useConfirm();
  const toast = useToast();
  const { data: members, error, loading, refetch } = useApi(() => api.workspaces.members(workspaceId), [workspaceId]);
  const [form, setForm] = useState({ email: '', role: 'STAFF' });
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const add = async (e) => {
    e.preventDefault();
    if (submitting) return;
    if (!form.email.trim()) {
      setFormError({ fieldErrors: { email: 'Enter the email they registered with' }, generalDetails: [] });
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await api.workspaces.addMember(workspaceId, { email: form.email.trim(), role: form.role });
      toast.success(`${form.email.trim()} added as ${form.role === 'OWNER' ? 'admin' : 'staff'}`);
      setForm({ email: '', role: 'STAFF' });
      refetch();
    } catch (err) {
      setFormError(err);
    } finally {
      setSubmitting(false);
    }
  };

  const changeRole = async (member, role) => {
    const ok = await confirm({
      title: 'Change role?',
      message: <p>{member.full_name} will become {role === 'OWNER' ? 'an admin with full access' : 'staff with limited access'}.</p>,
      confirmLabel: 'Change role',
    });
    if (!ok) return;
    try {
      await api.workspaces.changeRole(workspaceId, member.user_id, role);
      toast.success('Role updated');
    } catch (err) {
      toast.error(err.message);
    }
    refetch();
  };

  const remove = async (member) => {
    const ok = await confirm({
      title: 'Remove member?',
      message: <p>{member.full_name} will immediately lose access to {workspace.name}.</p>,
      confirmLabel: 'Remove',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.workspaces.removeMember(workspaceId, member.user_id);
      toast.success('Member removed');
    } catch (err) {
      toast.error(err.message);
    }
    refetch();
  };

  const fieldErrors = formError?.fieldErrors || {};
  return (
    <>
      <div className="page-header">
        <h1>Team</h1>
      </div>

      <section className="card">
        <h2>Add a team member</h2>
        <p className="muted small">They must first create a StockPilot account with their own email; then add them here.</p>
        <form onSubmit={add} noValidate className="form-grid">
          {formError && !fieldErrors.email && <div className="span-2"><ErrorBanner error={formError} /></div>}
          <TextField label="Their email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={fieldErrors.email} />
          <SelectField label="Role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="STAFF">Staff - view, adjust stock, manage orders</option>
            <option value="OWNER">Admin - full access</option>
          </SelectField>
          <div className="form-actions span-2">
            <button className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Adding…' : 'Add member'}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>Members</h2>
        <ErrorBanner error={error} onRetry={refetch} />
        {loading && !members && <Loading label="Loading team…" />}
        {members && members.length === 0 && <EmptyState title="No members" />}
        {members && members.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                  <th>
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.user_id}>
                    <td>
                      {m.full_name} {m.user_id === user.id && <span className="muted">(you)</span>}
                    </td>
                    <td>{m.email}</td>
                    <td>
                      <RoleBadge role={m.role} />
                    </td>
                    <td>{formatDate(m.created_at)}</td>
                    <td className="btn-row">
                      <button className="btn btn-small" onClick={() => changeRole(m, m.role === 'OWNER' ? 'STAFF' : 'OWNER')}>
                        Make {m.role === 'OWNER' ? 'staff' : 'admin'}
                      </button>
                      <button className="btn btn-small btn-danger-outline" onClick={() => remove(m)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
