import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CartProvider } from './context/CartContext';
import MenuPage from './pages/MenuPage';
import ItemDetailPage from './pages/ItemDetailPage';
import CartPage from './pages/CartPage';
import CheckoutPage from './pages/CheckoutPage';
import ConfirmationPage from './pages/ConfirmationPage';
import OrderStatusPage from './pages/OrderStatusPage';
import AdminLoginPage from './pages/AdminLoginPage';
import AdminOrdersPage from './pages/AdminOrdersPage';
import AdminMenuPage from './pages/AdminMenuPage';
import AdminItemFormPage from './pages/AdminItemFormPage';
import AdminSettingsPage from './pages/AdminSettingsPage';

function AdminGate({ children }: { children: JSX.Element }) {
  return localStorage.getItem('foodcart_admin') === 'yes' ? children : <Navigate to='/admin' replace />;
}

export default function App() {
  return <BrowserRouter>
    <CartProvider>
    <Routes>
      <Route path='/' element={<MenuPage />} />
      <Route path='/items/:id' element={<ItemDetailPage />} />
      <Route path='/cart' element={<CartPage />} />
      <Route path='/checkout' element={<CheckoutPage />} />
      <Route path='/confirmation/:id' element={<ConfirmationPage />} />
      <Route path='/status/:id' element={<OrderStatusPage />} />
      <Route path='/admin' element={<AdminLoginPage />} />
      <Route path='/admin/orders' element={<AdminGate><AdminOrdersPage /></AdminGate>} />
      <Route path='/admin/menu' element={<AdminGate><AdminMenuPage /></AdminGate>} />
      <Route path='/admin/menu/:id' element={<AdminGate><AdminItemFormPage /></AdminGate>} />
      <Route path='/admin/settings' element={<AdminGate><AdminSettingsPage /></AdminGate>} />
      <Route path='*' element={<Navigate to='/' replace />} />
    </Routes>
    </CartProvider>
  </BrowserRouter>;
}
