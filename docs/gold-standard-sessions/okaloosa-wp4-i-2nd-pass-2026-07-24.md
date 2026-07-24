# Okaloosa WP4 (letter I) — 2nd-pass independent re-verification

Dispatch f8de10ec-e7af-4ac2-9af7-6b7dd80c3809, work-package 4 of 5.

## Finding

This work-package's fix was already implemented and pushed to `main` earlier in
this same session as commit `c3b2545d` ("fix(gold-standard-okaloosa): WP4
letter I card completeness 66.7%->94.7% (38->54 of 57)"), which is an ancestor
of both this session's starting HEAD and `origin/main` — i.e. it was not lost,
not reverted, and is live.

This pass re-ran the diagnosis fresh (per the "adapt, don't blindly trust"
instruction) rather than assuming the prior result:

- Live `pencil_dod_evaluate_county('okaloosa')`: `I: card_complete=54 of 57
  (94.7%)`, `pass=false` (needs >=55/57). Identical before/after this pass —
  no drift, no regression.
- Re-derived the exact 3 failing rows from the RPC's own SQL (`v_zoning_gold_standard_card`
  join + address/geo/value NOT-NULL predicate):
  - `2024-CA-000470`, `2024-TDD-000089`: documented stale placeholder seed rows,
    no `parcel_id`, not recoverable. Left untouched.
  - `B4A-1299799` (Mary Esther, 172S24236000060030): address, geo (lat/lon),
    and assessed/market value are all real and present. Only gap is a
    `parcel_zones` zone-code match.
- Re-probed Mary Esther zoning live (not trusting the prior script's docstring
  claim at face value):
  - `Admin-Boundaries/Admin_Boundaries/MapServer/99/query` (city limits) —
    HTTP 400 "Failed to execute query" for every parameter combination tried
    (spatial point, envelope, plain `where=1=1`). Same failure on sibling
    layer `98` (City Limit PolyFill in the same service).
  - `Planning-Development/Zoning/MapServer/25/query` (County Zoning, the real
    layer — verified live that `28` is now "Coastal Construction Control
    Line", unrelated) — query succeeds but returns 0 features at this point,
    consistent with the point being inside incorporated city limits (county
    zoning does not apply there).
  - `LocalGovernment/Mary_Esther_EnerGov/MapServer/16/query` (City Limit
    PolyFill, Mary-Esther-specific service) — query succeeds:
    `ICLPY_CITY_CODE = "MARY ESTHER"`, confirming the parcel is inside
    incorporated Mary Esther.
  - Full `Mary_Esther_EnerGov` MapServer layer catalog inspected: Site
    Address, Property Data, Subdivisions, Parcels, Platted-Lots, Road
    Names/Centerline, Administrative Boundary, City Limit PolyFill, flood
    layers. No zoning layer, no zone field anywhere.
  - WebSearch confirms no public ArcGIS zoning REST endpoint exists for Mary
    Esther; only a Municode LDC text page and a city Community Development
    Dept contact page, neither queryable as live GIS data.

## Conclusion

No live, real GIS zoning source exists for Mary Esther. Per the fail-loud
invariant, `parcel_zones` was NOT populated with a guessed zone_code for
`B4A-1299799`. Letter I remains at `card_complete=54 of 57 (94.7%)`,
genuinely 1 row short of the >=55/57 PASS threshold — reported as a residual
gap, not rounded up or implied as passing.

## Residual gap (unchanged from prior pass)

- `B4A-1299799`: needs a `parcel_zones` entry for Mary Esther jurisdiction.
  Closing this requires either (a) a from-scratch Municode LDC scrape +
  manual district-boundary lookup for Mary Esther (out of scope for this
  bounded, single-row GIS-lever work-package), or (b) direct contact with
  Mary Esther's Community Development Dept for a machine-readable zoning
  layer that does not currently exist publicly.
- `2024-CA-000470`, `2024-TDD-000089`: stale placeholder seed rows, no
  parcel_id, not recoverable, out of scope (documented in prior fabrication
  purge migration).
