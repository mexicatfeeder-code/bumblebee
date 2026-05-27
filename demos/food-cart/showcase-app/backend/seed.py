import sqlite3
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from database import init_db, get_db, DB_PATH

# Remove existing DB for fresh seed
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

init_db()
conn = get_db()

# Categories
cats = [
    (1, 'Mains', 1),
    (2, 'Sides', 2),
    (3, 'Drinks', 3),
]
conn.executemany("INSERT INTO categories (id, name, sort_order) VALUES (?, ?, ?)", cats)

# Menu items (price in cents)
items = [
    ('Smash Burger', 'Double smashed patty, American cheese, pickles, special sauce', 1200, 1, 1),
    ('Street Tacos (3)', 'Carne asada, white onion, cilantro, salsa verde', 1100, 1, 2),
    ('BBQ Pulled Pork Sandwich', 'Slow-cooked pulled pork, house slaw, pickles, brioche bun', 1300, 1, 3),
    ('Crispy Chicken Wrap', 'Fried chicken, shredded lettuce, ranch, flour tortilla', 1050, 1, 4),
    ('Veggie Bowl', 'Roasted seasonal vegetables, brown rice, tahini drizzle', 950, 1, 5),
    ('Loaded Fries', 'Crispy fries, cheddar, jalapeños, sour cream', 800, 2, 1),
    ('Onion Rings', 'Beer-battered, golden crisp, chipotle dipping sauce', 700, 2, 2),
    ('Side Salad', 'Mixed greens, cherry tomatoes, cucumber, balsamic vinaigrette', 600, 2, 3),
    ('Lemonade', 'Fresh-squeezed, sweetened, over ice', 400, 3, 1),
    ('Sparkling Water', 'Canned sparkling water, assorted flavors', 300, 3, 2),
]
conn.executemany(
    "INSERT INTO menu_items (name, description, price, category_id, sort_order) VALUES (?, ?, ?, ?, ?)",
    items
)

# Settings (id=1, always)
conn.execute('''
    INSERT OR REPLACE INTO settings (id, cart_name, tagline, is_open, estimated_wait_minutes)
    VALUES (1, 'The Rolling Bite', 'Fresh food, made fast', 1, 10)
''')

conn.commit()
conn.close()
print(f"Seeded: {len(cats)} categories, {len(items)} items")
print(f"DB: {DB_PATH}")
