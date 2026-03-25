MISSION: Execute ALL CP2 tasks for ZoneWise parity. 7 fixes in one session.

REPO: breverdbidder/zonewise-web (for code fixes)

## TASK 1: Fix VAC-RES regression
Commit 7033264 may have re-introduced use-code-as-zoning fallback.
Check app/api/zoning-chat/route.ts — when zoning_assignments returns NO match for a parcel, the response must set zoning to null. 
NEVER use BCPAO USE_CODE or USE_CODE_DESCRIPTION as a zone_code.
When zoning is null, respond: "Zoning data is not yet available for this parcel... verify with [CITY] Planning Department"

## TASK 2: Fix DOR parcel ID URL encoding
Parcel IDs like "27 3701-50-7-4" contain spaces and special chars.
In app/api/zoning-report/route.ts and app/(dashboard)/report/[parcelId]/page.tsx:
- Use decodeURIComponent on the parcelId param
- In BCPAO GIS query, properly encode the parcel_id in the where clause
- Test: /api/zoning-report?parcelId=27%203701-50-7-4 must return data

## TASK 3: Fix address normalization
In app/api/zoning-chat/route.ts, the extractAddress function and BCPAO GIS fallback:
- "625 Ocean Street" must be normalized to query STREET_NAME='OCEAN' (strip the type suffix)
- The street type word list must include: street, drive, lane, avenue, boulevard, road, court, way, circle, place, terrace, trail, parkway, highway, causeway
- City extraction must work for "Satellite Beach" (two-word city names)

## TASK 4: Integrate ALL Brevard parcel IDs with report + PropertyCard
Currently the chatbot GIS fallback returns parcel data, but the PropertyCard "View Full Report" button must work with DOR-format parcel IDs.
In components/chat/PropertyCard.tsx:
- The "View Full Zoning Report" link must URL-encode the parcel_id: encodeURIComponent(parcelId)
- The "View on BCPAO" link must use TaxAcct (already available in the BCPAO lookup response)

## TASK 5: Ensure report/[parcelId] page works with both TaxAcct AND DOR format
In app/(dashboard)/report/[parcelId]/page.tsx:
- Accept both formats: pure digits (TaxAcct) AND DOR format (spaces, dashes, asterisks)
- For DOR format: query BCPAO GIS with PARCEL_ID='{decoded}'
- For TaxAcct: query BCPAO GIS with TaxAcct={number}
- Both must render the full ZoningReport component

## TASK 6: Add /report to middleware public routes (verify)
Check middleware.ts has '/report(.*)' and '/api/zoning-report(.*)' in isPublicRoute.
If missing, add them.

## TASK 7: Deploy and verify
After all fixes, push to main and trigger Vercel deploy:
curl -s -X POST "https://api.vercel.com/v13/deployments" -H "Authorization: Bearer ${VERCEL_TOKEN}" -H "Content-Type: application/json" -d '{"name":"zonewise-web","project":"prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E","target":"production","gitSource":{"type":"github","repoId":"1143596497","ref":"main"}}'

Verify:
1. curl -X POST https://zonewise.ai/api/zoning-chat with "625 Ocean Street Satellite Beach FL" — must find parcel 27 3701-50-7-4, NOT show VAC-RES
2. curl https://zonewise.ai/api/zoning-report?parcelId=27%203701-50-7-4 — must return JSON with 45 fields
3. curl -o /dev/null -w "%{http_code}" https://zonewise.ai/report/2614878 — must return 200

COMMIT: fix(CP2): VAC-RES regression + DOR encoding + address normalization + report integration

Push to breverdbidder/zonewise-web main using GH_PAT:
git remote set-url origin https://${GH_PAT}@github.com/breverdbidder/zonewise-web.git

Do NOT ask questions. Execute ALL 7 tasks. Push and deploy.
