import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { Settings, SettingsInput } from '../types';
import './styles/design-tokens.css';

export default function AdminSettingsPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<SettingsInput>({
    cart_name: '',
    tagline: '',
    is_open: true,
    estimated_wait_minutes: 10,
    admin_pin: '1234',
  });
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (localStorage.getItem('food-cart-admin') !== 'true') {
      navigate('/admin');
      return;
    }
    fetch('/api/settings').then((res) => res.json()).then((data: Settings) => setForm(data));
  }, [navigate]);

  const save = async () => {
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    setMessage('Settings saved.');
  };

  return (
    <div>
      <Header title="Food Cart Admin" subtitle="Settings" />
      <main style={{ maxWidth: 'var(--max-width)', margin: '0 auto', padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
          <Link to="/admin/orders" style={{ color: 'var(--color-primary)' }}>Orders</Link>
          <Link to="/admin/menu" style={{ color: 'var(--color-primary)' }}>Menu</Link>
          <Link to="/admin/settings" style={{ color: 'var(--color-primary)' }}>Settings</Link>
        </div>
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)', display: 'grid', gap: 'var(--space-3)' }}>
          <input value={form.cart_name} onChange={(e) => setForm({ ...form, cart_name: e.target.value })} placeholder="Cart name" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <input value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} placeholder="Tagline" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <input type="number" value={form.estimated_wait_minutes} onChange={(e) => setForm({ ...form, estimated_wait_minutes: Number(e.target.value) })} placeholder="Estimated wait minutes" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <input value={form.admin_pin} onChange={(e) => setForm({ ...form, admin_pin: e.target.value })} placeholder="Admin PIN" style={{ padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)` }} />
          <label style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
            <input type="checkbox" checked={form.is_open} onChange={(e) => setForm({ ...form, is_open: e.target.checked })} />
            Ordering Open
          </label>
          {message ? <div style={{ color: 'var(--color-success)' }}>{message}</div> : null}
          <button onClick={save} style={{ background: 'var(--color-primary)', color: 'var(--color-white)', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)' }}>Save Settings</button>
        </div>
      </main>
    </div>
  );
}
