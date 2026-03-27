# System-Specific Deployments

This folder contains deployment guides and artifacts for specific systems/platforms with unique constraints.

## Available Deployments

| Platform | Folder | Description | Status | Recommendation |
|----------|--------|-------------|--------|----------------|
| CasaOS Legacy | [`casaos-legacy/`](casaos-legacy/) | Older CasaOS versions (0.4.x) on ZimaBoard | Documented | ⚠️ Avoid if possible - upgrade to ZimaOS |

## Alternative: Upgrade Instead

If you have an old ZimaBoard with CasaOS 0.4.x, consider upgrading to **ZimaOS** instead:

- Better Docker Compose support
- Built-in terminal
- Easier deployments
- See [`deploy/zimaboard-new/`](../zimaboard-new/)

## Legacy Documentation

The [`casaos-legacy/`](casaos-legacy/) documentation exists for users who:
- Cannot upgrade their ZimaBoard hardware
- Cannot install ZimaOS
- Must use existing CasaOS 0.4.x installation

## Note on Railway

For Railway deployment (cloud hosting), see [`deploy/railway/`](../railway/) instead.

## Adding New System-Specific Deployment

To add a new constrained platform:

1. Create a new folder named after the platform
2. Include:
   - `README.md` - Step-by-step deployment guide
   - Form values or compose files for that platform
   - Any helper scripts
   - Troubleshooting section

3. Update the table above

## General Note

Most modern systems should use the standard deployment methods:
- **Docker Compose**: `docker compose up -d` - See main repo README
- **New ZimaBoard**: See [`deploy/zimaboard-new/`](../zimaboard-new/)
- **Railway Cloud**: See [`deploy/railway/`](../railway/)

This folder is specifically for platforms with unique constraints or limitations that prevent standard deployment.
