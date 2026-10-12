import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import ProductForm from '../components/ProductForm.jsx';
import { useCurrentWorkspace } from '../context/WorkspaceContext.jsx';
import { useToast } from '../context/ToastContext.jsx';

export default function ProductNew() {
  const { workspaceId, can } = useCurrentWorkspace();
  const navigate = useNavigate();
  const toast = useToast();

  if (!can('product:write')) {
    return (
      <div className="card center-card">
        <h1>Admins only</h1>
        <p className="muted">Only workspace admins can create products.</p>
        <Link to={`/w/${workspaceId}/products`}>Back to products</Link>
      </div>
    );
  }

  const create = async (payload) => {
    const product = await api.products.create(workspaceId, payload);
    toast.success(`Product “${product.name}” created`);
    navigate(`/w/${workspaceId}/products/${product.id}`);
  };

  return (
    <>
      <div className="page-header">
        <h1>New product</h1>
      </div>
      <div className="card">
        <ProductForm mode="create" submitLabel="Create product" onSubmit={create} onCancel={() => navigate(`/w/${workspaceId}/products`)} />
      </div>
    </>
  );
}
