# System-Specific Deployments

This folder contains deployment guides and artifacts for specific systems/platforms.

## Available Deployments

| Platform | Folder | Description | Status |
|----------|--------|-------------|--------|
| CasaOS Legacy | [`casaos-legacy/`](casaos-legacy/) | Older CasaOS versions (0.4.x) on ZimaBoard | Documented |

## Adding New System-Specific Deployment

To add a new platform:

1. Create a new folder named after the platform
2. Include:
   - `README.md` - Step-by-step deployment guide
   - Form values or compose files for that platform
   - Any helper scripts
   - Troubleshooting section

3. Update the table above

## General Note

Most modern systems can use the standard deployment methods:
- **Docker Compose**: `docker compose up -d`
- **Kubernetes**: Use Helm charts or raw manifests
- **Manual**: Systemd service files in `_etc/systemd/`

This folder is specifically for platforms with unique constraints or limitations.
