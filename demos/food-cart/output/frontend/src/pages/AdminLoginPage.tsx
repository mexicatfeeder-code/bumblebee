import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import { AdminAuthResponse } from '../types';
import './styles/design-tokens.css';

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    const res = await fetch('/api/settings/verify-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });
    const data: AdminAuthResponse = await res.json();
    if (data.success) {
      localStorage.setItem('food-cart-admin', 'true');
      navigate('/admin/orders');
      return;
    }
    setError('Invalid PIN.');
  };

  return (
    <div>
      <Header title="Food Cart" subtitle="Admin access" />
      <main style={{ maxWidth: 'var(--max-width)', margin: '0 auto', padding: 'var(--space-4)' }}>
        <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-5)' }}>
          <h1 style={{ marginTop: 0 }}>Enter Admin PIN</h1>
          <input
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            style={{ width: '100%', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', border: `1px solid var(--border-color)`, marginBottom: 'var(--space-3)' }}
          />
          {error ? <div style={{ color: 'var(--color-danger)', marginBottom: 'var(--space-3)' }}>{error}</div> : null}
          <button onClick={submit} style={{ width: '100%', background: 'var(--color-primary)', color: 'var(--color-white)', border: 'none', borderRadius: 'var(--radius-md)', padding: 'var(--space-3)' }}>
            Continue
          </button>
        </div>
      </main>
    </div>
  );
}
