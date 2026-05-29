import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { MenuItem } from '../types';

export default function AdminMenuPage() {
  const [items, setItems] = useState<MenuItem[]>([]);
  const load = () => fetch('/api/menu?available_only=false').then(r => r.json()).then(setItems);
  useEffect(load, []);
  async function toggle(item: MenuItem) {
    await fetch(`/api/menu/${item.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...item, available: !item.available }),
    });
    load();
  }
  async function del(id: number) {
    if (confirm('Delete item?')) {
      await fetch(`/api/menu/${id}`, { method: 'DELETE' });
      load();
    }
  }
  return (
    <Layout>
      <h1>Menu Manager</h1>
      <p>
        <Link to="/admin/orders">Orders</Link> &middot;{' '}
        <Link to="/admin/settings">Settings</Link>
      </p>
      <Link
        to="/admin/menu/new"
        style={{ ...buttonStyle, textDecoration: 'none' }}
      >
        Add Item
      </Link>
      {items.map(i => (
        <div
          key={i.id}
          style={{
            ...cardStyle,
            marginTop: 12,
            display: 'flex',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div>
            <h3>{i.name}</h3>
            <p>
              {i.category} &middot; {money(i.price)} &middot;{' '}
              {i.available ? 'Available' : '86\'d'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={() => toggle(i)} style={buttonStyle}>
              Toggle
            </button>
            <Link to={`/admin/menu/${i.id}`} style={buttonStyle}>
              Edit
            </Link>
            <button
              onClick={() => del(i.id)}
              style={{ ...buttonStyle, background: 'var(--color-danger)' }}
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </Layout>
  );
}
