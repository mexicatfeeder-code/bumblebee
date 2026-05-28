import React from 'react';
import '../styles/design-tokens.css';
import { MenuItem } from '../types';

interface MenuItemCardProps {
  item: MenuItem;
  quantity: number;
  onAdd: () => void;
  onRemove: () => void;
}

const MenuItemCard: React.FC<MenuItemCardProps> = ({ item, quantity, onAdd, onRemove }) => {
  const placeholderImage = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgdmlld0JveD0iMCAwIDMwMCAyMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjMwMCIgaGVpZ2h0PSIyMDAiIGZpbGw9IiNlNWU3ZWIiLz48cGF0aCBkPSJNMTUwIDEwMEMxNzIuMDgxIDEwMCAxOTAgMTE3LjkxOSAxOTAgMTQwVjE2MEgxMTBWMTQwQzExMCAxMTcuOTE5IDEyNy45MTkgMTAwIDE1MCAxMDBaIiBmaWxsPSIjY2FjZWRmIi8+PHBhdGggZD0iTTEwMCAxNjBWMjAwSDE5MFYxNjBIMTAwWiIgZmlsbD0iI2NhY2VkZiIvPjwvc3ZnPg==';

  return (
    <article className="menu-item-card">
      <div className="item-image-wrapper">
        {item.image ? (
          <img
            src={item.image.startsWith('http') ? item.image : `/uploads/menu_photos/${item.image}`}
            alt={item.name}
            className="item-image"
            loading="lazy"
          />
        ) : (
          <img
            src={placeholderImage}
            alt={item.name}
            className="item-image"
            loading="lazy"
          />
        )}
        {item.isPopular && (
          <span className="popular-badge">Popular</span>
        )}
        {!item.isAvailable && (
          <span className="unavailable-badge">Unavailable</span>
        )}
      </div>

      <div className="item-details">
        <div className="item-header">
          <h3 className="item-name">{item.name}</h3>
          <span className="item-price">${item.price.toFixed(2)}</span>
        </div>

        {item.description && (
          <p className="item-description">{item.description}</p>
        )}

        <div className="item-meta">
          {item.preparationTimeMinutes && (
            <span className="prep-time">
              ⏱ {item.preparationTimeMinutes} min
            </span>
          )}
          {item.calories && (
            <span className="calories">
              🔥 {item.calories} cal
            </span>
          )}
        </div>

        {item.tags && item.tags.length > 0 && (
          <div className="item-tags">
            {item.tags.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
        )}

        {item.allergens && item.allergens.length > 0 && (
          <div className="item-allergens">
            <span className="allergen-label">Allergens:</span>
            {item.allergens.map((allergen) => (
              <span key={allergen} className="allergen-tag">
                {allergen}
              </span>
            ))}
          </div>
        )}

        <div className="quantity-controls">
          <button
            className="qty-btn qty-decrease"
            onClick={onRemove}
            disabled={quantity === 0}
            aria-label={`Decrease quantity of ${item.name}`}
          >
            −
          </button>
          <span className="qty-display" aria-label={`Quantity: ${quantity}`}>
            {quantity}
          </span>
          <button
            className="qty-btn qty-increase"
            onClick={onAdd}
            aria-label={`Add ${item.name} to cart`}
          >
            +
          </button>
        </div>
      </div>
    </article>
  );
};

export default MenuItemCard;
