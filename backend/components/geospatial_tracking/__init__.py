# Code walkthrough:
# 1. api/ exposes historical analysis and veterinarian operational views.
# 2. services/spatial_timeline/service.py resolves scope and collects eligible sources.
# 3. services/spatial_timeline/engine.py builds grid scores and day-by-day map output.
# 4. services/stdbscan/ groups events close in space AND time for outbreak context.
# 5. schemas.py and domain/ retain record provenance, dates and quality labels.
# 6. repositories/ isolates storage; transport/ under services/ reuses snapshots.
# Spatial scores, geometric tendencies and modeled reach each have distinct meanings.
