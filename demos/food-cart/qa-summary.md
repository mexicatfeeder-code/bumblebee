# Technical Summary — Pop-Up Food Cart Ordering App

## Project Overview
A mobile-first food cart ordering app that lets walk-up customers browse a menu, build an order, and track its status in real-time. The cart operator manages everything from an admin panel. Runs entirely on local network with no cloud dependencies.

## Tech Stack
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS
- **Backend:** Python FastAPI + SQLite
- **Real-time:** WebSocket for order status and admin notifications
- **Photo storage:** Local disk (uploads directory), max 5MB per image
- **Port:** 8000 (backend serves both API and built frontend)

## Architecture Decisions
- **Single-port deployment** — FastAPI serves the built React frontend alongside the API, keeping deployment simple
- **SQLite** — no external database server needed, DB file lives alongside the app
- **WebSocket** — used for both customer order tracking and admin new-order notifications
- **Admin auth** — simple PIN-based access, configurable from settings (default: 1234)
- **Categories** — admin-managed (not hardcoded), supports create/edit/delete/reorder

## Scope (v1)
- Customer: browse menu by category, add to cart, submit order, track status
- Admin: full menu CRUD with photos, order management, daily sales summary, settings
- Real-time: order status updates (Preparing → Ready → Picked Up)
- Design: warm food-truck vibes, orange/yellow accents on light background, mobile-first

## Deferred to v2
- Payment processing
- Customer accounts and order history
- Multi-cart support
- Analytics beyond daily summary
- Dark mode
- Sound notifications

## Error Handling
- Network errors: show a non-blocking toast with retry option
- Photo upload failures: show error, keep the form state
- WebSocket disconnect: auto-reconnect with exponential backoff
- Invalid admin PIN: show error, no lockout in v1

## Open Questions
- None — all implementation decisions resolved during Q&A
