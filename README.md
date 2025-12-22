# ussd_app — Village Marketplace (Pilot)

USSD pilot app for a **local-first village marketplace**.

Users can discover trusted local services using **one simple USSD number**, without needing a smartphone or internet.

## Key features
- Browse local categories (shops, transport, services, farming, health, education)
- Add or update a business listing via USSD
- Listings are **village-based**, not anonymous
- **Phone numbers are hidden by default** and can be routed safely via the USSD gateway
- Designed to **maximize user safety and trust**
- One number gives access to everything in the local marketplace

## Safety & trust by design
- Local-first: services are listed by village and community
- No public exposure of phone numbers by default
- Interactions can be mediated through the USSD provider
- Logs are available to help resolve issues if needed
- Architecture allows future safety features (verification, trusted groups, limits by area)

## Technology
- Python + Flask
- Africa’s Talking USSD gateway
- SQLite database (local to the server)

## Notes
- Secrets and credentials are kept out of the repository
- Database files are intentionally not committed
- This repository contains **code only**, not data

## Status
Active pilot in Bumala. Designed to scale to other villages once the model is proven locally.
