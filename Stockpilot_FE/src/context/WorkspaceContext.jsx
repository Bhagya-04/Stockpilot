import { createContext, useContext, useMemo } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { useApi } from '../hooks/useApi.js';
import { can } from '../utils/permissions.js';
import { ErrorBanner, Loading } from '../components/States.jsx';

const WorkspaceContext = createContext(null);
const LAST_KEY = 'stockpilot.lastWorkspace';

export function rememberWorkspace(id) {
  try {
    localStorage.setItem(LAST_KEY, id);
  } catch {
    /* ignore */
  }
}

function lastWorkspace() {
  try {
    return localStorage.getItem(LAST_KEY);
  } catch {
    return null;
  }
}

/** Loads the signed-in user's workspaces once and exposes the one selected in the URL (/w/:workspaceId). */
export function WorkspacesProvider({ children }) {
  const { data, error, loading, refetch } = useApi(() => api.workspaces.list(), []);
  const value = useMemo(() => ({ workspaces: data || [], refetch }), [data, refetch]);
  if (loading && !data) return <Loading label="Loading your workspaces…" />;
  if (error) return <ErrorBanner error={error} onRetry={refetch} />;
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspaces() {
  return useContext(WorkspaceContext);
}

/** The current workspace + the user's role in it, from the URL. */
export function useCurrentWorkspace() {
  const { workspaceId } = useParams();
  const { workspaces } = useWorkspaces();
  const workspace = workspaces.find((w) => w.id === workspaceId) || null;
  return {
    workspace,
    workspaceId,
    role: workspace?.role || null,
    can: (permission) => can(workspace?.role, permission),
  };
}

/** "/" -> last used (or first) workspace, or the create-workspace page for brand-new users. */
export function WorkspaceRedirect() {
  const { workspaces } = useWorkspaces();
  if (workspaces.length === 0) return <Navigate to="/workspaces/new" replace />;
  const target = workspaces.find((w) => w.id === lastWorkspace()) || workspaces[0];
  return <Navigate to={landingPath(target)} replace />;
}

export function landingPath(workspace) {
  return `/w/${workspace.id}/${workspace.role === 'OWNER' ? 'dashboard' : 'orders'}`;
}
