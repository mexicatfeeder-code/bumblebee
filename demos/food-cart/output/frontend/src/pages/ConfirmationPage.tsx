import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { Order, Settings } from '../types';

export default function ConfirmationPage() {
  const { id } = useParams();
  const [order, setOrder] = useState<Order | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  useEffect(() => { fetch(`/api/orders/${id}`).then(r=>r.json()).then(setOrder); fetch('/api/settings').then(r=>r.json()).then(setSettings); }, [id]);
  if (!order) return <Layout><p>Loading confirmation...</p></Layout>;
  return <Layout><div style={{ ...cardStyle, textAlign: 'center' }}>
    <h1>Order {order.order_number}</h1>
    <h2>Thanks, {order.customer_name}!</h2>
    <p>Estimated wait: {settings?.estimated_wait_minutes || 10} minutes.</p>
    {order.items.map(i => <p key={i.id}>{i.quantity} x {i.item_name} — {money(i.quantity * i.item_price)}</p>)}
    <p>We will call your name when it is ready.</p>
    <Link to={`/status/${order.id}`} style={{ ...buttonStyle, textDecoration: 'none' }}>Track status</Link>
  </div></Layout>;
}
