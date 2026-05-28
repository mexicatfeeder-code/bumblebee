// Shared TypeScript types for the Food Cart application
// Used by both frontend and backend

// ─── Order Status ────────────────────────────────────────────────────────────

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'preparing'
  | 'ready'
  | 'delivered'
  | 'cancelled';

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  preparing: 'Preparing',
  ready: 'Ready',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
};

// ─── Menu Category ───────────────────────────────────────────────────────────

export interface MenuCategory {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  displayOrder: number;
  isActive: boolean;
}

// ─── Menu Item ───────────────────────────────────────────────────────────────

export interface MenuItem {
  id: string;
  categoryId: string;
  name: string;
  description: string;
  price: number;
  image?: string;
  isAvailable: boolean;
  isPopular?: boolean;
  tags?: string[];
  preparationTimeMinutes?: number;
  allergens?: string[];
  calories?: number;
  displayOrder: number;
}

// ─── Order Item ──────────────────────────────────────────────────────────────

export interface OrderItem {
  menuItemId: string;
  menuItemName: string;
  quantity: number;
  unitPrice: number;
  specialInstructions?: string;
}

// ─── Order ───────────────────────────────────────────────────────────────────

export interface Order {
  id: string;
  customerName: string;
  customerPhone?: string;
  customerEmail?: string;
  items: OrderItem[];
  subtotal: number;
  tax: number;
  total: number;
  status: OrderStatus;
  specialInstructions?: string;
  createdAt: string;
  updatedAt: string;
  estimatedReadyTime?: string;
}

// ─── Order Summary (for list views) ─────────────────────────────────────────

export interface OrderSummary {
  id: string;
  customerName: string;
  total: number;
  status: OrderStatus;
  createdAt: string;
  itemCount: number;
}

// ─── Cart Item ───────────────────────────────────────────────────────────────

export interface CartItem extends OrderItem {
  menuItem: MenuItem;
}

// ─── App Settings ────────────────────────────────────────────────────────────

export interface AppSettings {
  appName: string;
  currency: string;
  currencySymbol: string;
  taxRate: number;
  minOrderAmount: number;
  maxPreparationTimeMinutes: number;
  enableOnlinePayments: boolean;
  enablePickup: boolean;
  enableDelivery: boolean;
  deliveryRadiusKm?: number;
  deliveryFee: number;
  businessHours?: BusinessHours;
  contactPhone?: string;
  contactEmail?: string;
  address?: string;
}

// ─── Business Hours ─────────────────────────────────────────────────────────

export interface BusinessHours {
  monday: TimeRange | null;
  tuesday: TimeRange | null;
  wednesday: TimeRange | null;
  thursday: TimeRange | null;
  friday: TimeRange | null;
  saturday: TimeRange | null;
  sunday: TimeRange | null;
}

export interface TimeRange {
  open: string; // HH:mm format
  close: string; // HH:mm format
}

// ─── API Response Types ─────────────────────────────────────────────────────

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ─── Filter & Sort Types ────────────────────────────────────────────────────

export type SortDirection = 'asc' | 'desc';

export interface SortConfig<T> {
  key: keyof T;
  direction: SortDirection;
}

export interface MenuFilters {
  categoryId?: string;
  searchQuery?: string;
  availableOnly?: boolean;
  priceRange?: { min: number; max: number };
  tags?: string[];
}

export interface OrderFilters {
  status?: OrderStatus;
  dateFrom?: string;
  dateTo?: string;
  customerName?: string;
}

// ─── Theme Types ─────────────────────────────────────────────────────────────

export type ThemeMode = 'light' | 'dark';

export interface ThemeColors {
  primary: string;
  secondary: string;
  accent: string;
  background: string;
  surface: string;
  text: string;
  textSecondary: string;
  border: string;
  success: string;
  warning: string;
  error: string;
}

// ─── Notification Types ─────────────────────────────────────────────────────

export type NotificationType = 'info' | 'success' | 'warning' | 'error';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  duration?: number; // milliseconds, 0 for persistent
  createdAt: string;
}

// ─── User Types ──────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'staff' | 'customer';

export interface User {
  id: string;
  name: string;
  email: string;
  phone?: string;
  role: UserRole;
  isActive: boolean;
  createdAt: string;
}
