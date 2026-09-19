# Friend UX Integration — LandGuard

The friend's Command Palette, Project Quick View, Scope Dock, Role Journey, and Why LandGuard surfaces were already present in the current LandGuard source. This patch therefore avoids overwriting the newer acquisition-risk/governance work and only improves the integration:

- Project Quick View now fetches the current acquisition-readiness result and shows the primary blocker + next milestone.
- Quick View no longer contains the stale statement that GIS and ML are disconnected.
- Command Palette can navigate directly to Why LandGuard.
- Why LandGuard no longer says the model uses illustrative synthetic data; it now accurately describes the real PAIMANA schedule baseline and the separate acquisition-risk/friction/readiness lane.
- No backend, ML, RBAC, intervention, or database logic is overwritten.
