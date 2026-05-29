import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { useCart } from '../context/CartContext';
import { Order } from '../types';

export default function CheckoutPage() {
  const { lines, subtotal, clear } = useCart();
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  async function place() {
    setBusy(true);
    setError('');
    const res = await fetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        customer_name: name,
        items: lines.map(l => ({ item_id: l.item.id, quantity: l.quantity })),
      }),
    });
    if (!res.ok) {
      const e = await res.json();
      setError(e.detail || 'Could not place order');
      setBusy(false);
      return;
    }
    const order: Order = await res.json();
    clear();
    nav(`/confirmation/${order.id}`);
  }

  return (
    <Layout>
      <h1>Checkout</h1>
      {lines.length === 0 ? (
        <p>Your cart is empty.</p>
      ) : (
        <div style={cardStyle}>
          {lines.map(l => (
            <p key={l.item.id}>
              {l.quantity} x {l.item.name} — {money(l.quantity * l.item.price)}
            </p>
          ))}
          <h2>Total: {money(subtotal)}</h2>
          <label>
            Pickup name
            <br />
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              style={{
                padding: 12,
                borderRadius: 10,
                border: '1px solid var(--color-primary)',
                width: '100%',
                maxWidth: 360,
              }}
            />
          </label>
          {error && <p style={{ color: 'var(--color-danger)' }}>{error}</p>}
          <br />
          <button
            disabled={busy || !name.trim()}
            onClick={place}
            style={buttonStyle}
          >
            {busy ? 'Placing...' : 'Place Order'}
          </button>
        </div>
      )}
    </Layout>
  );
}
