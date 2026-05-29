import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle } from '../components/Layout';
import { Category, MenuItem } from '../types';

export default function AdminItemFormPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [cats, setCats] = useState<Category[]>([]);
  const [form, setForm] = useState({ name: '', description: '', price: '0', category_id: 1, photo_url: '', available: true, sort_order: 0 });

  useEffect(() => {
    fetch('/api/categories')
      .then(r => r.json())
      .then(c => {
        setCats(c);
        if (c[0]) setForm(f => ({ ...f, category_id: c[0].id }));
      });
    if (id && id !== 'new') {
      fetch(`/api/menu/${id}`)
        .then(r => r.json())
        .then((m: MenuItem) => setForm({ ...m, price: String(m.price) }));
    }
  }, [id]);

  async function upload(file: File) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/uploads', { method: 'POST', body: fd });
    const data = await res.json();
    setForm(f => ({ ...f, photo_url: data.url }));
  }

  async function save() {
    const body = {
      ...form,
      price: Number(form.price),
      category_id: Number(form.category_id),
      sort_order: Number(form.sort_order),
    };
    await fetch(
      id && id !== 'new' ? `/api/menu/${id}` : '/api/menu',
      {
        method: id && id !== 'new' ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );
    nav('/admin/menu');
  }

  const input = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }));

  return (
    <Layout>
      <div style={cardStyle}>
        <h1>{id === 'new' ? 'Add' : 'Edit'} Item</h1>
        <input
          placeholder='Name'
          value={form.name}
          onChange={e => input('name', e.target.value)}
          style={{ padding: 10, width: '100%', marginBottom: 8 }}
        />
        <textarea
          placeholder='Description'
          value={form.description}
          onChange={e => input('description', e.target.value)}
          style={{ padding: 10, width: '100%', marginBottom: 8 }}
        />
        <input
          placeholder='Price cents'
          value={form.price}
          onChange={e => input('price', e.target.value)}
          style={{ padding: 10, width: '100%', marginBottom: 8 }}
        />
        <select
          value={form.category_id}
          onChange={e => input('category_id', Number(e.target.value))}
          style={{ padding: 10, width: '100%', marginBottom: 8 }}
        >
          {cats.map(c => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          placeholder='Photo URL'
          value={form.photo_url}
          onChange={e => input('photo_url', e.target.value)}
          style={{ padding: 10, width: '100%', marginBottom: 8 }}
        />
        <input
          type='file'
          accept='image/*'
          onChange={e => e.target.files?.[0] && upload(e.target.files[0])}
        />
        <p>
          <label>
            <input
              type='checkbox'
              checked={form.available}
              onChange={e => input('available', e.target.checked)}
            />{' '}
            Available
          </label>
        </p>
        <button onClick={save} style={buttonStyle}>
          Save
        </button>
      </div>
    </Layout>
  );
}
