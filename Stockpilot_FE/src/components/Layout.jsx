import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import {
  landingPath,
  rememberWorkspace,
  useCurrentWorkspace,
  useWorkspaces,
} from '../context/WorkspaceContext.jsx';
import { can as can2 } from '../utils/permissions.js';
import WorkspaceSwitcher from './WorkspaceSwitcher.jsx';

// Simple stroke icons (24x24) so the sidebar needs no icon library.
const ICONS = {
  dashboard: 'M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6v-9h-6v9zm0-16v5h6V4h-6z',
  products: 'M21 8l-9-5-9 5v8l9 5 9-5V8zM3.3 7.7L12 12.5l8.7-4.8M12 12.5V21',
  inventory: 'M12 8v5l3 2M21 12a9 9 0 11-3-6.7M21 4v5h-5',
  orders: 'M6 2h12v20l-3-2-3 2-3-2-3 2V2zm3 6h6m-6 4h6',
  members: 'M16 20v-1.5a3.5 3.5 0 00-3.5-3.5h-5A3.5 3.5 0 004 18.5V20M10 12a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm10 8v-1.5a3.5 3.5 0 00-2.5-3.35M16 5.2a3.5 3.5 0 010 6.6',
};

function Icon({ name }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

const NAV = [
  { to: 'dashboard', label: 'Dashboard', icon: 'dashboard', permission: 'dashboard:read' },
  { to: 'products', label: 'Products', icon: 'products', permission: 'product:read' },
  { to: 'inventory', label: 'Stock history', icon: 'inventory', permission: 'inventory:read' },
  { to: 'orders', label: 'Orders', icon: 'orders', permission: 'order:read' },
  { to: 'members', label: 'Team', icon: 'members', permission: 'member:manage' },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { workspaces } = useWorkspaces();
  const { workspaceId, workspace, can } = useCurrentWorkspace();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (workspace) rememberWorkspace(workspace.id);
  }, [workspace]);

  // Keep the section (products/orders/…) when switching workspace, if the role allows it.
  const switchWorkspace = (id) => {
    if (id === '__new') return navigate('/workspaces/new');
    const target = workspaces.find((w) => w.id === id);
    const section = location.pathname.split('/')[3];
    const allowed = NAV.find((n) => n.to === section && can2(target.role, n.permission));
    navigate(allowed ? `/w/${id}/${section}` : landingPath(target));
  };

  const initials = user.full_name
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar">
        <div className="side-top">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true">
              ▣
            </span>
            StockPilot
          </span>

          <div className="side-user">
            <span className="avatar" aria-hidden="true">
              {initials}
            </span>
            <div className="side-user-text">
              <span className="user-name">{user.full_name}</span>
              <button className="link-button" onClick={logout}>
                Sign out
              </button>
            </div>
          </div>
        </div>

        <div className="workspace-switch">
          <span className="side-label">Workspace</span>
          <WorkspaceSwitcher workspaces={workspaces} current={workspace} onSelect={switchWorkspace} />
        </div>

        {workspace && (
          <nav className="side-nav" aria-label="Main">
            {NAV.filter((item) => can(item.permission)).map((item) => (
              <NavLink
                key={item.to}
                to={`/w/${workspaceId}/${item.to}`}
                className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        )}
      </aside>

      <main id="main" className="content">
        {workspaceId && !workspace ? (
          <div className="card center-card">
            <h1>Workspace not found</h1>
            <p className="muted">It doesn&apos;t exist, or you are not a member of it.</p>
          </div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
