import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { useCart } from '../context/CartContext';
import { Category, MenuItem, Settings } from '../types';

export default function MenuPage() {
  const [items, setItems] = useState<MenuItem[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [cat, setCat] = useState<number | 'all'>('all');
  const [settings, setSettings] = useState<Settings | null>(null);
  const { addItem } = useCart();
  useEffect(() => { Promise.all([fetch('/api/menu').then(r=>r.json()), fetch('/api/categories').then(r=>r.json()), fetch('/api/settings').then(r=>r.json())]).then(([m,c,s]) => { setItems(m); setCats(c); setSettings(s); }); }, []);
  const shown = cat === 'all' ? items : items.filter(i => i.category_id === cat);
  return <Layout>
    <section style={{ ...cardStyle, background: 'var(--bg-card)', marginBottom: 16 }}>
      <h1 style={{ margin: 0, fontSize: 34 }}>{settings?.cart_name || 'Food Cart'}</h1>
      <p style={{ fontSize: 18 }}>{settings?.tagline || 'Fresh food made fast'}</p>
      {settings && !settings.is_open && <b style={{ color: 'var(--color-danger)' }}>We are closed right now. Please check back soon.</b>}
    </section>
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginBottom: 16 }}>
      <button onClick={() => setCat('all')} style={{ ...buttonStyle, background: cat === 'all' ? 'var(--color-primary)' : 'var(--text-secondary)' }}>All</button>
      {cats.map(c => <button key={c.id} onClick={() => setCat(c.id)} style={{ ...buttonStyle, background: cat === c.id ? 'var(--color-primary)' : 'var(--text-secondary)' }}>{c.name}</button>)}
    </div>
    {shown.length === 0 && <p>No menu items available.</p>}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 16 }}>
      {shown.map(item => <div key={item.id} style={cardStyle}>
        {item.photo_url && <img src={item.photo_url} style={{ width: '100%', height: 150, objectFit: 'cover', borderRadius: 14 }} />}
        <h2>{item.name}</h2><p>{item.description}</p><b>{money(item.price)}</b>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <Link to={`/items/${item.id}`} style={{ ...buttonStyle, background: 'var(--text-secondary)', textDecoration: 'none' }}>Details</Link>
          <button disabled={!settings?.is_open} onClick={() => addItem(item)} style={buttonStyle}>Add</button>
        </div>
      </div>)}
    </div>
  </Layout>;
}
