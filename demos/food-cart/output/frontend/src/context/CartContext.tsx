import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { CartLine, MenuItem } from '../types';

type CartContextValue = {
  lines: CartLine[];
  count: number;
  subtotal: number;
  addItem: (item: MenuItem, quantity?: number) => void;
  setQuantity: (itemId: number, quantity: number) => void;
  removeItem: (itemId: number) => void;
  clear: () => void;
};

const CartContext = createContext<CartContextValue | undefined>(undefined);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(() => {
    try { return JSON.parse(localStorage.getItem('foodcart_cart') || '[]'); } catch { return []; }
  });
  useEffect(() => { localStorage.setItem('foodcart_cart', JSON.stringify(lines)); }, [lines]);
  const addItem = (item: MenuItem, quantity = 1) => setLines(prev => {
    const existing = prev.find(l => l.item.id === item.id);
    if (existing) return prev.map(l => l.item.id === item.id ? { ...l, quantity: l.quantity + quantity } : l);
    return [...prev, { item, quantity }];
  });
  const setQuantity = (itemId: number, quantity: number) => setLines(prev => quantity < 1 ? prev.filter(l => l.item.id !== itemId) : prev.map(l => l.item.id === itemId ? { ...l, quantity } : l));
  const removeItem = (itemId: number) => setLines(prev => prev.filter(l => l.item.id !== itemId));
  const clear = () => setLines([]);
  const value = useMemo(() => ({
    lines,
    count: lines.reduce((s, l) => s + l.quantity, 0),
    subtotal: lines.reduce((s, l) => s + l.quantity * l.item.price, 0),
    addItem, setQuantity, removeItem, clear
  }), [lines]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used inside CartProvider');
  return ctx;
}
