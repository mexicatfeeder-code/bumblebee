import { Link } from 'react-router-dom';
import Layout, { buttonStyle, cardStyle, money } from '../components/Layout';
import { useCart } from '../context/CartContext';

export default function CartPage() {
  const { lines, subtotal, setQuantity, removeItem, clear } = useCart();
  return <Layout>
    <h1>Your Cart</h1>
    {lines.length === 0 ? <div style={cardStyle}><p>Your cart is empty.</p><Link to='/' style={buttonStyle}>Browse menu</Link></div> : <>
      {lines.map(l => <div key={l.item.id} style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', marginBottom: 12, gap: 12 }}>
        <div><h3>{l.item.name}</h3><p>{money(l.item.price)} each</p></div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={() => setQuantity(l.item.id, l.quantity - 1)} style={buttonStyle}>-</button><b>{l.quantity}</b>
          <button onClick={() => setQuantity(l.item.id, l.quantity + 1)} style={buttonStyle}>+</button>
          <button onClick={() => removeItem(l.item.id)} style={{ ...buttonStyle, background: '#b42318' }}>Remove</button>
        </div>
      </div>)}
      <div style={cardStyle}><h2>Subtotal: {money(subtotal)}</h2><div style={{ display: 'flex', gap: 12 }}><button onClick={clear} style={{ ...buttonStyle, background: '#704214' }}>Clear</button><Link to='/checkout' style={{ ...buttonStyle, textDecoration: 'none' }}>Checkout</Link></div></div>
    </>}
  </Layout>;
}
