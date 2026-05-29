import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle } from '../components/Layout';
import { Settings } from '../types';

export default function AdminSettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    fetch('/api/settings')
      .then((r) => r.json())
      .then(setS);
  }, []);
  if (!s) return <Layout><p>Loading...</p></Layout>;
  const set = (k: keyof Settings, v: any) => setS({ ...s, [k]: v });
  async function save() {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(s),
    });
    setS(await res.json());
    setSaved(true);
  }
  return (
    <Layout>
      <div style={cardStyle}>
        <h1>Settings</h1>
        <p>
          <Link to='/admin/orders'>Orders</Link> ·{' '}
          <Link to='/admin/menu'>Menu</Link>
        </p>
        <label>
          Cart name
          <input
            value={s.cart_name}
            onChange={(e) => set('cart_name', e.target.value)}
            style={{
              display: 'block',
              padding: 10,
              width: '100%',
              marginBottom: 8,
            }}
          />
        </label>
        <label>
          Tagline
          <input
            value={s.tagline}
            onChange={(e) => set('tagline', e.target.value)}
            style={{
              display: 'block',
              padding: 10,
              width: '100%',
              marginBottom: 8,
            }}
          />
        </label>
        <label>
          Estimated wait minutes
          <input
            type='number'
            value={s.estimated_wait_minutes}
            onChange={(e) =>
              set('estimated_wait_minutes', Number(e.target.value))
            }
            style={{
              display: 'block',
              padding: 10,
              width: '100%',
              marginBottom: 8,
            }}
          />
        </label>
        <label>
          Admin PIN
          <input
            value={s.admin_pin}
            onChange={(e) => set('admin_pin', e.target.value)}
            style={{
              display: 'block',
              padding: 10,
              width: '100%',
              marginBottom: 8,
            }}
          />
        </label>
        <p>
          <label>
            <input
              type='checkbox'
              checked={s.is_open}
              onChange={(e) => set('is_open', e.target.checked)}
            />{' '}
            Open for ordering
          </label>
        </p>
        <button onClick={save} style={buttonStyle}>
          Save
        </button>
        {saved && <b style={{ marginLeft: 12 }}>Saved</b>}
      </div>
    </Layout>
  );
}
