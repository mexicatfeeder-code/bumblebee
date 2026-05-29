import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { useCart } from '../context/CartContext';
import { MenuItem } from '../types';

export default function ItemDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { addItem } = useCart();
  const [item, setItem] = useState<MenuItem | null>(null);
  const [qty, setQty] = useState(1);
  const [error, setError] = useState('');
  useEffect(() => {
    fetch(`/api/menu/${id}`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(setItem)
      .catch(() => setError('Item not found'));
  }, [id]);
  if (error) return <Layout><p>{error}</p><Link to='/'>Back to menu</Link></Layout>;
  if (!item) return <Layout><p>Loading...</p></Layout>;
  return <Layout>
    <div style={cardStyle}>
      {item.photo_url && <img src={item.photo_url} style={{ width: '100%', maxHeight: 360, objectFit: 'cover', borderRadius: 18 }} />}
      <h1>{item.name}</h1>
      <p>{item.description}</p>
      <h2>{money(item.price)}</h2>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={() => setQty(Math.max(1, qty - 1))} style={buttonStyle}>-</button>
        <b>{qty}</b>
        <button onClick={() => setQty(qty + 1)} style={buttonStyle}>+</button>
        <button onClick={() => { addItem(item, qty); nav('/cart'); }} style={buttonStyle}>Add to cart</button>
      </div>
    </div>
  </Layout>;
}
