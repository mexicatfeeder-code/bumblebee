import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Header from '../components/Header';
import { Category, MenuItem, MenuItemInput } from '../types';
import './styles/design-tokens.css';

const emptyForm: MenuItemInput = {
  name: '',
  description: '',
  price: 0,
  category_id: 0,
  photo_url: '',
  available: true,
  sort_order: 0,
};

export default function AdminItemFormPage() {
  const navigate = useNavigate();
  const { itemId } = useParams();
  const isEdit = itemId !== 'new';
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState<MenuItemInput>(emptyForm);

  useEffect(() => {
    if (localStorage.getItem('food-cart-admin') !== 'true') {
      navigate('/admin');
      return;
    }
    fetch('/api/categories').then((res) => res.json()).then((data: Category[]) => {
      setCategories(data);
      if (data.length > 0) {
        setForm((current) => ({ ...current, category_id: current.category_id || data[0].id }));
      }
    });
    if (isEdit) {
      fetch(`/api/menu-items/${itemId}`).then((res) => res.json()).then((item: MenuItem) => {
        setForm({
          name: item.name,
          description: item.description,
          price: item.price,
          category_id: item.category_id,
          photo_url: item.photo_url,
          available: item.available,
          sort_order: item.sort_order,
        });
      });
    }
  }, [navigate, isEdit, itemId]);

  const uploadPhoto = async (file: File) => {
    const data = new FormData();
    data.append('file', file);
    const res = await fetch('/api/uploads', { method: 'POST', body: data });
    const result = await res.json();
    setForm((current) => ({ ...current, photo_url: result.url }));
  };

  const save = async () => {
    const url = isEdit ? `/api/menu-items/${itemId}` : '/api/menu-items';
    const method = isEdit ? 'PUT' : 'POST';
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    navigate('/admin/menu');
  };

  return (
    <div>
      <Header title="Food Cart Admin" subtitle={isEdit ? 'Edit item' : 'Add item'} />
      <main style={{ maxWidth: 'var(--max-width)', margin: '0 auto', padding: 'var(--space-4)' }}>
        <Link to="/admin/menu" style={{ color: 'var(--color-primary)' }}>← Back to menu</Link>
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', marginTop: 'var(--space-4)', display: 'grid', gap: 'var(--space-3)' }}>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)`, minHeight: '100px' }} />
          <input type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} placeholder="Price in cents" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })} style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }}>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <input value={form.photo_url} onChange={(e) => setForm({ ...form, photo_url: e.target.value })} placeholder="Photo URL" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <input type="file" accept="image/*" onChange={(e) => e.target.files && uploadPhoto(e.target.files[0])} />
          <input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} placeholder="Sort order" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <label style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
            <input type="checkbox" checked={form.available} onChange={(e) => setForm({ ...form, available: e.target.checked })} />
            Available
          </label>
          <button onClick={save} style={{ background: 'var(--color-primary)', color: 'var(--color-white)', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)' }}>Save Item</button>
        </div>
      </main>
    </div>
  );
}
