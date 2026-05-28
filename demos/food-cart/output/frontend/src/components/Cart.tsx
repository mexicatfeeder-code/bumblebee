import React, { useCallback, useMemo } from 'react';
import '../styles/design-tokens.css';

export interface CartItem {
  menuItemId: string;
  menuItemName: string;
  quantity: number;
  unitPrice: number;
}

interface CartProps {
  items: CartItem[];
  onUpdateQuantity: (menuItemId: string, newQuantity: number) => void;
  onSubmitOrder: () => void;
  isSubmitting?: boolean;
}

const Cart: React.FC<CartProps> = ({ items, onUpdateQuantity, onSubmitOrder, isSubmitting = false }) => {
  const totalPrice = useMemo(() => {
    return items.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0);
  }, [items]);

  const handleIncrement = useCallback(
    (item: CartItem) => {
      onUpdateQuantity(item.menuItemId, item.quantity + 1);
    },
    [onUpdateQuantity]
  );

  const handleDecrement = useCallback(
    (item: CartItem) => {
      if (item.quantity > 1) {
        onUpdateQuantity(item.menuItemId, item.quantity - 1);
      }
    },
    [onUpdateQuantity]
  );

  const handleRemove = useCallback(
    (item: CartItem) => {
      onUpdateQuantity(item.menuItemId, 0);
    },
    [onUpdateQuantity]
  );

  const handleCheckout = useCallback(() => {
    if (items.length > 0 && !isSubmitting) {
      onSubmitOrder();
    }
  }, [items, isSubmitting, onSubmitOrder]);

  if (items.length === 0) {
    return (
      <aside className="cart-container" aria-label="Shopping Cart">
        <h2 className="cart-title">Your Cart</h2>
        <div className="cart-empty">
          <p className="cart-empty-message">Your cart is empty</p>
          <p className="cart-empty-hint">Browse the menu and add items to get started!</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="cart-container" aria-label="Shopping Cart">
      <h2 className="cart-title">Your Cart</h2>

      <div className="cart-items" role="list">
        {items.map((item) => (
          <div key={item.menuItemId} className="cart-item" role="listitem">
            <div className="cart-item-info">
              <span className="cart-item-name">{item.menuItemName}</span>
              <span className="cart-item-unit-price">${item.unitPrice.toFixed(2)}</span>
            </div>

            <div className="cart-item-controls">
              <button
                type="button"
                className="cart-qty-btn cart-qty-btn--remove"
                onClick={() => handleRemove(item)}
                aria-label={`Remove ${item.menuItemName}`}
              >
                −
              </button>

              <span className="cart-item-quantity" aria-label={`Quantity: ${item.quantity}`}>
                {item.quantity}
              </span>

              <button
                type="button"
                className="cart-qty-btn cart-qty-btn--add"
                onClick={() => handleIncrement(item)}
                aria-label={`Add another ${item.menuItemName}`}
              >
                +
              </button>
            </div>

            <div className="cart-item-line-total">
              ${(item.unitPrice * item.quantity).toFixed(2)}
            </div>
          </div>
        ))}
      </div>

      <div className="cart-summary">
        <div className="cart-total-row">
          <span className="cart-total-label">Total</span>
          <span className="cart-total-value">${totalPrice.toFixed(2)}</span>
        </div>

        <button
          type="button"
          className="cart-submit-btn"
          onClick={handleCheckout}
          disabled={isSubmitting}
          aria-label={isSubmitting ? 'Submitting order...' : 'Submit order'}
        >
          {isSubmitting ? 'Submitting...' : 'Submit Order'}
        </button>
      </div>
    </aside>
  );
};

export default Cart;
