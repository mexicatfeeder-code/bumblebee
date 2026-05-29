from database import get_db, init_db

PHOTOS = [
    'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38',
    'https://images.unsplash.com/photo-1550547660-d9450f859349',
    'https://images.unsplash.com/photo-1565958011703-44f9829ba187',
    'https://images.unsplash.com/photo-1551504734-5ee1c4a1479b'
]

def seed():
    init_db()
    db = get_db()
    if db.execute('SELECT COUNT(*) c FROM categories').fetchone()['c'] == 0:
        cats = [('Tacos', 1), ('Bowls', 2), ('Sides', 3), ('Drinks', 4)]
        db.executemany('INSERT INTO categories (name, sort_order) VALUES (?,?)', cats)
    if db.execute('SELECT COUNT(*) c FROM menu_items').fetchone()['c'] == 0:
        items = [
            ('Carnitas Taco','Slow pork, salsa verde, onion, cilantro',450,1,PHOTOS[0],1,1),
            ('Mushroom Taco','Roasted mushrooms, crema, pickled onion',425,1,PHOTOS[0],1,2),
            ('Chicken Tinga Taco','Smoky chicken, cotija, lime',475,1,PHOTOS[0],1,3),
            ('Street Corn Bowl','Rice, beans, corn, crema, chili lime',1050,2,PHOTOS[2],1,1),
            ('Barbacoa Bowl','Braised beef, rice, beans, salsa roja',1250,2,PHOTOS[1],1,2),
            ('Chips & Guac','House chips with fresh guacamole',650,3,PHOTOS[3],1,1),
            ('Elote Cup','Sweet corn, crema, cotija, tajin',550,3,PHOTOS[3],1,2),
            ('Agua Fresca','Rotating fruit agua fresca',400,4,PHOTOS[2],1,1)
        ]
        db.executemany('''INSERT INTO menu_items
        (name,description,price,category_id,photo_url,available,sort_order) VALUES (?,?,?,?,?,?,?)''', items)
    db.execute('''INSERT OR IGNORE INTO settings
    (id,cart_name,tagline,is_open,estimated_wait_minutes,admin_pin)
    VALUES (1,'Sunset Taco Cart','Fresh street food, made fast',1,12,'1234')''')
    db.commit()
    db.close()

if __name__ == '__main__':
    seed()
