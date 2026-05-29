import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { MenuItem, MenuItemInput } from '../types';
import './styles/design-tokens.css';

export default function AdminMenuPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<MenuItem[]>([]);

  useEffect(() => {
    if (localStorage.getItem('food-cart-admin') !== 'true') {
      navigate('/admin');
      return;
    }
    fetch('/api/menu-items').then((res) => res.json()).then(setItems);
  }, [navigate]);

  const toggleAvailability = async (item: MenuItem) => {
    const payload: MenuItemInput = {
      name: item.name,
      description: item.description,
      price: item.price,
      category_id: item.category_id,
      photo_url: item.photo_url,
      available: !item.available,
      sort_order: item.sort_order,
    };
    const res = await fetch(`/api/menu-items/${item.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const updated = await res.json();
    setItems((current) => current.map((entry) => (entry.id === item.id ? updated : entry)));
  };

  const deleteItem = async (itemId: number) => {
    await fetch(`/api/menu-items/${itemId}`, { method: 'DELETE' });
    setItems((current) => current.filter((entry) => entry.id !== itemId));
  };

  return (
    <div>
      <Header title="Food Cart Admin" subtitle="Menu manager" />
      <main style={{ maxWidth: 'var(--max-width)', margin: '0 auto', padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
          <Link to="/admin/orders" style={{ color: 'var(--color-primary)' }}>Orders</Link>
          <Link to="/admin/menu" style={{ color: 'var(--color-primary)' }}>Menu</Link>
          <Link to="/admin/settings" style={{ color: 'var(--color-primary)' }}>Settings</Link>
        </div>
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <Link to="/admin/menu/new" style={{ textDecoration: 'none', background: 'var(--color-primary)', color: 'var(--color-white)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', display: 'inline-block' }}>
            Add New Item
          </Link>
        </div>
        <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
          {items.map((item) => (
            <div key={item.id} style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', display: 'flex', justifyContent: 'space-between', gap: 'var(--space-3)' }}>
              <div>
                <div style={{ fontWeight: 700 }}>{item.name}</div>
                <div>{item.category_name}</div>
                <div>${(item.price / 100).toFixed(2)}</div>
                <div style={{ color: item.available ? 'var(--color-success)' : 'var(--color-danger)' }}>{item.available ? 'Available' : 'Unavailable'}</div>
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                <Link to={`/admin/menu/${item.id}`} style={{ textDecoration: 'none', background: 'var(--color-secondary)', color: 'var(--color-primary)', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)' }}>Edit</Link>
                <button onClick={() => toggleAvailability(item)} style={{ border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-warning)' }}>Toggle</button>
                <button onClick={() => deleteItem(item.id)} style={{ border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-3) var(--space-4)', background: 'var(--color-danger-light)', color: 'var(--color-danger)' }}>Delete</button>
              </div>
            </div>
          ))}
          {items.length === 0 ? <div>No menu items found.</div> : null}
        </div>
      </main>
    </div>
  );
}
