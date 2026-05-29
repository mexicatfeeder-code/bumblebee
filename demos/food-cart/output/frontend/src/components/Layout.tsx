import { Link } from 'react-router-dom';
import { useCart } from '../context/CartContext';

export default function Layout({ children }: { children: React.ReactNode }) {
  const { count } = useCart();
  return <div style={{ minHeight: '100vh', background: 'var(--bg-page)', color: 'var(--text-primary)' }}>
    <header style={{ position: 'sticky', top: 0, zIndex: 2, background: 'var(--color-primary)', padding: 16, boxShadow: '0 2px 10px var(--shadow-color)' }}>
      <div style={{ maxWidth: 980, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link to='/' style={{ color: 'white', fontWeight: 900, fontSize: 22, textDecoration: 'none' }}>Food Cart</Link>
        <nav style={{ display: 'flex', gap: 12 }}>
          <Link to='/cart' style={{ color: 'white', fontWeight: 800 }}>Cart ({count})</Link>
          <Link to='/admin' style={{ color: 'white' }}>Admin</Link>
        </nav>
      </div>
    </header>
    <main style={{ maxWidth: 980, margin: '0 auto', padding: 16 }}>{children}</main>
    <footer style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>Pay at the cart. We will call your name when ready.</footer>
  </div>;
}

export function money(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

export const buttonStyle: React.CSSProperties = { background: 'var(--color-primary)', color: 'white', border: 0, borderRadius: 12, padding: '10px 14px', fontWeight: 800, cursor: 'pointer' };
export const cardStyle: React.CSSProperties = { background: 'var(--bg-card)', borderRadius: 18, padding: 16, boxShadow: 'var(--shadow-card)', border: '1px solid var(--border-light)' };
