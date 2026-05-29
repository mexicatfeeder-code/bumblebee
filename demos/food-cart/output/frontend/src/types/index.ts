export type OrderStatus = 'received' | 'in_progress' | 'ready' | 'picked_up';

export interface Category {
  id: number;
  name: string;
  sort_order: number;
}

export interface MenuItem {
  id: number;
  name: string;
  description: string;
  price: number;
  category_id: number;
  category: string;
  photo_url: string;
  available: boolean;
  sort_order: number;
}

export interface OrderItem {
  id: number;
  order_id: number;
  item_id: number;
  item_name: string;
  item_price: number;
  quantity: number;
}

export interface Order {
  id: number;
  order_number: string;
  customer_name: string;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
}

export interface Settings {
  cart_name: string;
  tagline: string;
  is_open: boolean;
  estimated_wait_minutes: number;
  admin_pin: string;
}

export interface CartLine {
  item: MenuItem;
  quantity: number;
}

export interface CreateOrderItem {
  item_id: number;
  quantity: number;
}
