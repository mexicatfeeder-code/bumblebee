import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle } from '../components/Layout';
import { Order, OrderStatus } from '../types';

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  useEffect(() => {
    fetch('/api/orders?active_only=true').then(r => r.json()).then(setOrders);
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/api/ws/admin`);
    ws.onmessage = e => {
      const o = JSON.parse(e.data);
      const rest = orders.filter(x => x.id !== o.id);
      setOrders([o, ...rest].filter(x => x.status !== 'picked_up'));
    };
    return () => ws.close();
  }, [orders]);
  async function setStatus(id: number, status: OrderStatus) {
    const res = await fetch(`/api/orders/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    const o = await res.json();
    setOrders(prev => prev.map(x => x.id === id ? o : x).filter(x => x.status !== 'picked_up'));
  }
  return (
    <Layout>
      <h1>Orders</h1>
      <p>
        <Link to='/admin/menu'>Menu</Link> · <Link to='/admin/settings'>Settings</Link>
      </p>
      {orders.length === 0 && <div style={cardStyle}>No active orders.</div>}
      {orders.map(o => (
        <div key={o.id} style={{ ...cardStyle, marginBottom: 12 }}>
          <h2>{o.order_number} — {o.customer_name}</h2>
          <b>{o.status.replace('_', ' ')}</b>
          {o.items.map(i => (
            <p key={i.id}>{i.quantity} x {i.item_name}</p>
          ))}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={() => setStatus(o.id, 'in_progress')} style={buttonStyle}>In Progress</button>
            <button onClick={() => setStatus(o.id, 'ready')} style={buttonStyle}>Ready</button>
            <button onClick={() => setStatus(o.id, 'picked_up')} style={{ ...buttonStyle, background: 'var(--color-accent)' }}>Picked Up</button>
          </div>
        </div>
      ))}
    </Layout>
  );
}
