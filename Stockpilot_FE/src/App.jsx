import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import { Loading } from './components/States.jsx';
import { useAuth } from './context/AuthContext.jsx';
import { useCurrentWorkspace, WorkspaceRedirect, WorkspacesProvider } from './context/WorkspaceContext.jsx';
import Dashboard from './pages/Dashboard.jsx';
import InventoryHistory from './pages/InventoryHistory.jsx';
import Login from './pages/Login.jsx';
import Members from './pages/Members.jsx';
import OrderDetail from './pages/OrderDetail.jsx';
import OrderNew from './pages/OrderNew.jsx';
import Orders from './pages/Orders.jsx';
import ProductDetail from './pages/ProductDetail.jsx';
import ProductNew from './pages/ProductNew.jsx';
import Products from './pages/Products.jsx';
import Register from './pages/Register.jsx';
import WorkspaceCreate from './pages/WorkspaceCreate.jsx';

/** Everything behind this requires a signed-in user; unauthenticated visitors are sent to /login. */
function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <Loading label="Signing you in…" />;
  if (status !== 'authed') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return (
    <WorkspacesProvider>
      <Outlet />
    </WorkspacesProvider>
  );
}

/** UI guard for pages a role can't use (the API enforces this too). */
function RequirePermission({ permission, children }) {
  const { can, workspaceId } = useCurrentWorkspace();
  if (can(permission)) return children;
  return (
    <div className="card center-card">
      <h1>Admins only</h1>
      <p className="muted">Your role doesn&apos;t have access to this page.</p>
      <Link to={`/w/${workspaceId}/orders`}>Go to orders</Link>
    </div>
  );
}

function NotFound() {
  return (
    <div className="card center-card">
      <h1>Page not found</h1>
      <Link to="/">Go home</Link>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<WorkspaceRedirect />} />

        <Route element={<Layout />}>
          <Route path="/workspaces/new" element={<WorkspaceCreate />} />
        </Route>

        <Route path="/w/:workspaceId" element={<Layout />}>
          <Route index element={<WorkspaceRedirectInside />} />
          <Route path="dashboard" element={<RequirePermission permission="dashboard:read"><Dashboard /></RequirePermission>} />
          <Route path="products" element={<Products />} />
          <Route path="products/new" element={<ProductNew />} />
          <Route path="products/:productId" element={<ProductDetail />} />
          <Route path="inventory" element={<InventoryHistory />} />
          <Route path="orders" element={<Orders />} />
          <Route path="orders/new" element={<OrderNew />} />
          <Route path="orders/:orderId" element={<OrderDetail />} />
          <Route path="members" element={<RequirePermission permission="member:manage"><Members /></RequirePermission>} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function WorkspaceRedirectInside() {
  const { workspace } = useCurrentWorkspace();
  if (!workspace) return null;
  return <Navigate to={workspace.role === 'OWNER' ? 'dashboard' : 'orders'} replace />;
}
