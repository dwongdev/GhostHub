# Controllers

Backend controllers are structured by product domain, matching the domain boundaries in `app/services/`.

GhostHub controllers use the SPECTER runtime from the `specter-runtime` package. Controllers subclass `specter.Controller` and register HTTP routes through the provided router, with socket/event integration kept inside SPECTER-owned controller/service boundaries.

## Domains

- **`admin/`**: Admin configuration, system controls, maintenance tools, and visibility overrides.
- **`core/`**: Application-level connections and main application endpoints.
- **`ghoststream/`**: The GhostStream service endpoints.
- **`media/`**: Category management, media discovery, cataloging, progress, and subtitles.
- **`storage/`**: Drive mounts, file management, and uploads.
- **`streaming/`**: Watch-party sync and chat functionality.
- **`system/`**: Low-level device controls, tunneling, transferring, and TV casting.

All controllers are registered during application boot through `app/app_bootstrap.py` and `app/controllers/__init__.py`.
