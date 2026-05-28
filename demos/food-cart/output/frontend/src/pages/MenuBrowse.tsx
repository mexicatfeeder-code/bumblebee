import React, { useState, useEffect, useCallback } from 'react';
import '../styles/design-tokens.css';
import { MenuCategory, MenuItem } from '../types';
import MenuItemCard from '../components/MenuItemCard';

const API_BASE = '/api';

interface CartItem {
  menuItemId: string;
  menuItemName: string;
  quantity: number;
  unitPrice: number;
}

const MenuBrowse: React.FC = () => {
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const fetchMenuData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [categoriesRes, itemsRes] = await Promise.all([
        fetch(`${API_BASE}/categories`),
        fetch(`${API_BASE}/menu-items`),
      ]);

      if (!categoriesRes.ok) {
        throw new Error(`Failed to fetch categories: ${categoriesRes.statusText}`);
      }
      if (!itemsRes.ok) {
        throw new Error(`Failed to fetch menu items: ${itemsRes.statusText}`);
      }

      const categoriesData: MenuCategory[] = await categoriesRes.json();
      const itemsData: MenuItem[] = await itemsRes.json();

      setCategories(categoriesData.filter((c) => c.isActive).sort((a, b) => a.displayOrder - b.displayOrder));
      setMenuItems(itemsData.filter((item) => item.isAvailable));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMenuData();
  }, [fetchMenuData]);

  const addToCart = useCallback((item: MenuItem) => {
    setCart((prevCart) => {
      const existing = prevCart.find((ci) => ci.menuItemId === item.id);
      if (existing) {
        return prevCart.map((ci) =>
          ci.menuItemId === item.id
            ? { ...ci, quantity: ci.quantity + 1 }
            : ci
        );
      }
      return [
        ...prevCart,
        {
          menuItemId: item.id,
          menuItemName: item.name,
          quantity: 1,
          unitPrice: item.price,
        },
      ];
    });
  }, []);

  const removeFromCart = useCallback((menuItemId: string) => {
    setCart((prevCart) => {
      const existing = prevCart.find((ci) => ci.menuItemId === menuItemId);
      if (!existing) return prevCart;
      if (existing.quantity <= 1) {
        return prevCart.filter((ci) => ci.menuItemId !== menuItemId);
      }
      return prevCart.map((ci) =>
        ci.menuItemId === menuItemId
          ? { ...ci, quantity: ci.quantity - 1 }
          : ci
      );
    });
  }, []);

  const getCartQuantity = useCallback(
    (menuItemId: string) => {
      const item = cart.find((ci) => ci.menuItemId === menuItemId);
      return item ? item.quantity : 0;
    },
    [cart]
  );

  const cartItemCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  const cartTotal = cart.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0);

  const groupedItems = categories.map((category) => ({
    category,
    items: menuItems
      .filter((item) => item.categoryId === category.id)
      .sort((a, b) => a.displayOrder - b.displayOrder),
  }));

  const displayedGroups = selectedCategory
    ? groupedItems.filter((g) => g.category.id === selectedCategory)
    : groupedItems;

  if (loading) {
    return (
      <div className="menu-browse-loading">
        <p>Loading menu...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="menu-browse-error">
        <p>Error: {error}</p>
        <button onClick={fetchMenuData}>Retry</button>
      </div>
    );
  }

  return (
    <div className="menu-browse">
      <header className="menu-browse-header">
        <h1>Our Menu</h1>
        {cartItemCount > 0 && (
          <div className="cart-summary">
            <span className="cart-count">{cartItemCount} item{cartItemCount !== 1 ? 's' : ''}</span>
            <span className="cart-total">${cartTotal.toFixed(2)}</span>
          </div>
        )}
      </header>

      <nav className="category-nav">
        <button
          className={`category-btn ${!selectedCategory ? 'active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat.id}
            className={`category-btn ${selectedCategory === cat.id ? 'active' : ''}`}
            onClick={() => setSelectedCategory(cat.id)}
          >
            {cat.icon && <span className="category-icon">{cat.icon}</span>}
            {cat.name}
          </button>
        ))}
      </nav>

      <main className="menu-content">
        {displayedGroups.length === 0 ? (
          <p className="no-items">No items available.</p>
        ) : (
          displayedGroups.map(({ category, items }) => (
            <section key={category.id} className="menu-section">
              <div className="section-header">
                <h2>{category.name}</h2>
                {category.description && (
                  <p className="section-description">{category.description}</p>
                )}
              </div>
              {items.length === 0 ? (
                <p className="no-items">No items in this category.</p>
              ) : (
                <div className="items-grid">
                  {items.map((item) => (
                    <MenuItemCard
                      key={item.id}
                      item={item}
                      quantity={getCartQuantity(item.id)}
                      onAdd={() => addToCart(item)}
                      onRemove={() => removeFromCart(item.id)}
                    />
                  ))}
                </div>
              )}
            </section>
          ))
        )}
      </main>
    </div>
  );
};

export default MenuBrowse;
