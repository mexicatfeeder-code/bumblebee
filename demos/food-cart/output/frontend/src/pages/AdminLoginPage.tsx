import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle } from '../components/Layout';

export default function AdminLoginPage() {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const nav = useNavigate();

  async function login() {
    const res = await fetch('/api/auth/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });
    const data = await res.json();
    if (data.ok) {
      localStorage.setItem('foodcart_admin', 'yes');
      nav('/admin/orders');
    } else {
      setError('Invalid PIN');
    }
  }

  return (
    <Layout>
      <div style={{ ...cardStyle, maxWidth: 420, margin: '40px auto' }}>
        <h1>Admin Login</h1>
        <input
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="PIN"
          style={{
            padding: 12,
            borderRadius: 10,
            width: '100%',
            border: '1px solid var(--color-primary)',
            boxSizing: 'border-box',
          }}
        />
        {error && <p style={{ color: 'var(--color-danger)' }}>{error}</p>}
        <br />
        <button onClick={login} style={buttonStyle}>
          Enter
        </button>
      </div>
    </Layout>
  );
}
