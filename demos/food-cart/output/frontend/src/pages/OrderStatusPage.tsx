import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import Layout, { cardStyle } from '../components/Layout';
import { Order, OrderStatus } from '../types';

const labels: OrderStatus[] = ['received', 'in_progress', 'ready'];

export default function OrderStatusPage() {
  const { id } = useParams();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    fetch(`/api/orders/${id}`).then(r => r.ok ? r.json() : Promise.reject()).then(setOrder).catch(() => setError('Order not found'));
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/api/ws/orders/${id}`);
    ws.onmessage = e => setOrder(JSON.parse(e.data));
    return () => ws.close();
  }, [id]);
  if (error) return <Layout><p>{error}</p></Layout>;
  if (!order) return <Layout><p>Loading...</p></Layout>;
  const idx = labels.indexOf(order.status as OrderStatus);
  return <Layout><div style={cardStyle}>
    <h1>Order {order.order_number}</h1><h2>Status: {order.status.replace('_', ' ')}</h2>
    <div style={{ display: 'grid', gap: 12 }}>
      {labels.map((s, i) => <div key={s} style={{ padding: 16, borderRadius: 12, background: i <= idx ? 'var(--color-primary)' : 'var(--bg-card)' }}>{i <= idx ? '✓ ' : ''}{s.replace('_', ' ')}</div>)}
    </div>
    {order.status === 'ready' && <h2 style={{ color: 'var(--color-success)' }}>Ready! Please come to the cart.</h2>}
  </div></Layout>;
}
