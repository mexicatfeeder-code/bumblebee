# Pop-Up Food Cart Ordering App — PRD

## Overview
A lightweight ordering app for a pop-up food cart that lets customers browse the menu, customize orders, and submit them — all from their phone or a tablet at the counter. The cart operator manages the menu, tracks orders, and updates order status from an admin panel.

## User Stories

### Customer
- Browse the menu by category (Mains, Sides, Drinks)
- See item photos, descriptions, and prices
- Add items to a cart with quantity controls
- Submit an order and see a confirmation with order number
- View order status in real-time (Preparing → Ready → Picked Up)

### Cart Operator (Admin)
- Add, edit, and remove menu items (name, description, price, category, photo)
- Toggle items as available/sold out
- View incoming orders with timestamps
- Update order status with one click
- See daily sales summary
- Configure cart name and operating hours

## Key Requirements
- Mobile-first responsive design
- Works on local network (no cloud dependency)
- Real-time order status updates (WebSocket)
- Simple SQLite database (no external DB server)
- Photo upload for menu items
- No authentication for customers (walk-up ordering)
- Admin panel behind a simple PIN/password

## Non-Goals (v1)
- Payment processing
- Multi-cart support
- Customer accounts/history
- Analytics beyond daily summary
- Delivery tracking
