import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { Order } from '../types';
import './styles/design-tokens.css';

export default function AdminOrdersPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);

  useEffect(() => {
    if (localStorage.getItem('food-cart-admin') !== 'true') {
      navigate('/admin');
      return;
    }
    const load = () => fetch('/api/orders').then((res) => res.json()).then(setOrders);
    load();
    const interval = window.setInterval(load, 5000);
    return () => window.clearInterval(interval);
  }, [navigate]);

  const updateStatus = async (orderId: number, status: string) => {
    const res = await fetch(`/api/orders/${orderId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    const updated = await res.json();
    setOrders((current) => current.map((order) => (order.id === orderId ? updated : order)));
  };

  return (
    <div>
      <Header title="Food Cart Admin" subtitle="Orders dashboard" />
      <main style={{ maxWidth: 'var(--max-width)', margin: '0 auto', padding: 'var(--space-4)' }}>
        <div style={{ display: 'flex', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
          <Link to="/admin/orders" style={{ color: 'var(--color-primary)' }}>Orders</Link>
          <Link to="/admin/menu" style={{ color: 'var(--color-primary)' }}>Menu</Link>
          <Link to="/admin/settings" style={{ color: 'var(--color-primary)' }}>Settings</Link>
        </div>
        <div style={{ display: 'grid', gap: 'var(--space-3)' }}>
          {orders.map((order) => (
            <div key={order.id} style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}>
                <div>
                  <strong>{order.order_number}</strong> — {order.customer_name}
                </div>
                <div style={{ color: 'var(--color-primary)', fontWeight: 700 }}>{order.status}</div>
              </div>
              <div style={{ marginBottom: 'var(--space-3)' }}>
                {order.items.map((item) => `${item.item_name} x ${item.quantity}`).join(', ')}
              </div>
              <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                <button onClick={() => updateStatus(order.id, 'in_progress')} style={{ border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', background: 'var(--color-secondary-light)' }}>Mark In Progress</button>
                <button onClick={() => updateStatus(order.id, 'ready')} style={{ border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', background: 'var(--color-secondary)' }}>Mark Ready</button>
                <button onClick={() => updateStatus(order.id, 'picked_up')} style={{ border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-2) var(--space-3)', background: 'var(--bg-secondary)' }}>Picked Up</button>
              </div>
            </div>
          ))}
          {orders.length === 0 ? <div>No orders yet.</div> : null}
        </div>
      </main>
    </div>
  );
}
