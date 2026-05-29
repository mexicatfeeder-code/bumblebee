/**
 * MenuBrowse - Customer-facing menu browsing page.
 * Displays menu items grouped by category with photos, descriptions, and prices.
 */

import { useState, useEffect, useCallback } from "react";
import { MenuItem, MenuCategory } from "../types/shared";

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const API_BASE = "/api";

async function fetchCategories(): Promise<MenuCategory[]> {
  const res = await fetch(`${API_BASE}/categories`);
  if (!res.ok) throw new Error("Failed to fetch categories");
  const data = await res.json();
  return data.map((c: any) => ({
    id: String(c.id),
    name: c.name,
    description: c.description,
    icon: c.icon,
    sortOrder: c.sort_order ?? 0,
  }));
}

async function fetchMenuItems(): Promise<MenuItem[]> {
  const res = await fetch(`${API_BASE}/menu`);
  if (!res.ok) throw new Error("Failed to fetch menu items");
  const raw = await res.json();
  const data = Array.isArray(raw) ? raw : (raw.items || []);
  return data.map((item: any) => ({
    id: String(item.id),
    categoryId: String(item.category_id),
    name: item.name,
    description: item.description,
    price: item.price / 100, // convert cents to dollars
    image: item.photo_url,
    isAvailable: item.available,
    tags: item.tags,
    allergens: item.allergens,
  }));
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/**
 * Renders a single menu item card.
 */
function MenuItemCard({ item }: { item: MenuItem }) {
  return (
    <div className="menu-item-card">
      <div className="menu-item-image-wrapper">
        {item.image ? (
          <img
            src={item.image}
            alt={item.name}
            className="menu-item-image"
            loading="lazy"
          />
        ) : (
          <div className="menu-item-image-placeholder">
            <span>No image</span>
          </div>
        )}
        {!item.isAvailable && (
          <div className="menu-item-unavailable-overlay">
            <span>Unavailable</span>
          </div>
        )}
      </div>
      <div className="menu-item-info">
        <h4 className="menu-item-name">{item.name}</h4>
        {item.description && (
          <p className="menu-item-description">{item.description}</p>
        )}
        <div className="menu-item-footer">
          <span className="menu-item-price">${item.price.toFixed(2)}</span>
          {item.tags && item.tags.length > 0 && (
            <div className="menu-item-tags">
              {item.tags.map((tag) => (
                <span key={tag} className="menu-item-tag">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Renders a single category section with its items.
 */
function CategorySection({
  category,
  items,
  isExpanded,
  onToggle,
}: {
  category: MenuCategory;
  items: MenuItem[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const availableItems = items.filter((item) => item.isAvailable);

  return (
    <section className="category-section">
      <button
        className="category-header"
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-controls={`category-${category.id}`}
      >
        <span className="category-icon">{category.icon && <span>{category.icon}</span>}</span>
        <h2 className="category-name">{category.name}</h2>
        {category.description && (
          <span className="category-description">{category.description}</span>
        )}
        <span className="category-count">{availableItems.length} items</span>
        <span className={`category-chevron ${isExpanded ? "expanded" : ""}`}>
          ▼
        </span>
      </button>

      {isExpanded && (
        <div
          className={`category-items ${isExpanded ? "visible" : ""}`}
          id={`category-${category.id}`}
        >
          {availableItems.length === 0 ? (
            <p className="no-items-message">No items available in this category.</p>
          ) : (
            availableItems.map((item) => (
              <MenuItemCard key={item.id} item={item} />
            ))
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function MenuBrowse() {
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set()
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cats, items] = await Promise.all([
        fetchCategories(),
        fetchMenuItems(),
      ]);
      setCategories(cats);
      setMenuItems(items);
      // Auto-expand the first category
      if (cats.length > 0) {
        setExpandedCategories(new Set([cats[0].id]));
      }
    } catch (err: any) {
      setError(err.message || "Failed to load menu");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleCategory = useCallback((categoryId: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(categoryId)) {
        next.delete(categoryId);
      } else {
        next.add(categoryId);
      }
      return next;
    });
  }, []);

  // Group menu items by category
  const itemsByCategory = menuItems.reduce<Record<string, MenuItem[]>>(
    (acc, item) => {
      if (!acc[item.categoryId]) {
        acc[item.categoryId] = [];
      }
      acc[item.categoryId].push(item);
      return acc;
    },
    {}
  );

  if (loading) {
    return (
      <div className="menu-browse-page">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading menu...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="menu-browse-page">
        <div className="error-state">
          <p className="error-message">⚠️ {error}</p>
          <button className="retry-button" onClick={loadData}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="menu-browse-page">
      <header className="menu-browse-header">
        <h1>Our Menu</h1>
        <p>Browse our delicious offerings by category</p>
      </header>

      <main className="menu-browse-main">
        {categories.length === 0 ? (
          <p className="no-categories-message">No categories available.</p>
        ) : (
          categories.map((category) => (
            <CategorySection
              key={category.id}
              category={category}
              items={itemsByCategory[category.id] ?? []}
              isExpanded={expandedCategories.has(category.id)}
              onToggle={() => toggleCategory(category.id)}
            />
          ))
        )}
      </main>
    </div>
  );
}
