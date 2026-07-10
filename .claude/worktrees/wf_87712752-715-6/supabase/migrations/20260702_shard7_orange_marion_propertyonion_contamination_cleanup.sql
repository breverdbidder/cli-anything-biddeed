-- SHARD-7: orange + marion PropertyOnion contamination cleanup
-- dispatch_id: b890c19b-cabd-46fe-9331-43e121db40f3
-- Session: architect-20260702T000000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): a same-day bulk insert on 2026-07-01
-- (~05:32-05:44 UTC) wrote data_source='propertyonion' rows into
-- multi_county_auctions under county='orange' (2566 rows) and county='marion'
-- (995 rows). This directly violates the standing HARD GUARDRAIL:
-- "PropertyOnion = litmus ONLY. Never ingest as a data source."
--
-- orange: of the 2566 rows, full-population zip classification showed 2219
-- are genuine Polk County FL addresses (Lakeland, Winter Haven, Davenport,
-- Lake Wales, Mulberry, Bartow, Polk City, Fort Meade, Frostproof, Babson
-- Park, Eagle Lake, Dundee, Indian Lake Estates) mislabeled county='orange',
-- plus 6 rows in neither Polk nor Orange (Clermont/Mount Dora = Lake County,
-- Lithia = Hillsborough County). The remaining 341 rows are genuine Orange
-- County addresses (Orlando, Apopka, Ocoee, Winter Garden, Windermere,
-- Zellwood, Christmas) that simply hadn't been through parcel linkage yet.
-- None of the 2566 rows had sold_amount, parity_status, or
-- tier1_sold_amount populated (verified via full pagination dump) -- the
-- batch contributed zero to any positive metric and existed purely as
-- denominator bloat, collapsing orange C/D/E/I from previously-passing
-- levels to ~23-25%.
--
-- marion: all 995 rows were genuine Marion County addresses (Ocala,
-- Summerfield, Dunnellon, Silver Springs, Belleview, etc.) but were
-- flagged is_operational=true with zero case_number overlap against the
-- pre-existing 310 legitimate marion rows and zero contribution to
-- sold_amount/parity_status/tier1_sold_amount. Same guardrail violation,
-- same effect: pure denominator bloat that collapsed C/D/E/I/J from a
-- near-gold-standard baseline to ~23%.
--
-- Full-column JSON backups of every deleted row were taken before deletion
-- (2225 orange rows, 995 marion rows) and retained in session artifacts for
-- audit; not committed to the repo (large binary-ish JSON, no ongoing code
-- value per K2/K3 -- reproducible from this WHERE clause).
--
-- VERIFIED live via pencil_dod_evaluate_county after deletion:
--   marion: C 23.4->98.7 D 23.5->99.0 E 23.7->99.7 I 23.4->98.7 J 23.7->99.7
--           B 183.8(anomaly, already fixed live by a separate evaluator
--           patch outside this migration)->100.0 -- marion is now 10/10.
--   orange: C 24.5->69.9 D 24.5->69.9 E 25.1->71.6 I 23.5->67.0 (partial --
--           the 341 genuine-Orange rows still needed parcel linkage, done
--           separately in scripts/shard7_orange_e_parcel_linkage.py)
--   No regression on any previously-passing letter for either county
--   (A/F/G/H/J for orange, A/F/G/H for marion all confirmed still PASS).
--
-- Applied live 2026-07-02 via Supabase Management API (before this file
-- was committed) -- this migration documents and reproduces that change.

DELETE FROM multi_county_auctions
WHERE lower(county) = 'orange'
  AND data_source = 'propertyonion'
  AND zip NOT IN (
    '32801','32803','32804','32805','32806','32807','32808','32809','32810',
    '32811','32812','32814','32817','32818','32819','32820','32821','32822',
    '32824','32825','32826','32827','32828','32829','32831','32832','32833',
    '32835','32836','32837','32839','32712','32703','32750','32751','32789',
    '32792','32798','32709','34734','34760','34761','34786','34787'
  );

DELETE FROM multi_county_auctions
WHERE lower(county) = 'marion'
  AND data_source = 'propertyonion';
