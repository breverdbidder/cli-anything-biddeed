# HOLDOUT.md — written by validator role in CP4

This file is a stub. CP0 (issue #19777) only installs the skeleton — the
holdout set (hidden acceptance cases the builder role never sees, used by
the validator to judge a PR without the builder having been able to write
directly to the test) is authored in CP4, once the mutation-set/validator
work lands (`docs/gtm/META.md` §8).

Until CP4:
- This path is reserved and access-restricted per `.gitattributes` (see
  `gtm-checkout=validator-only` attribute on `.factory/gtm/locks/**` and
  `.factory/gtm/holdout/**` at repo root) and
  `factory/gtm/builder_checkout.sh` (the sparse-checkout rule any
  builder-role workflow step must run before checking out this repo).
- `factory/gtm/test_holdout_negative.sh` is the negative test proving a
  builder-role checkout (sparse-checkout with this path excluded) cannot
  read this file, while an unrestricted (validator-role) checkout can.
- Nothing in this file is used by `factory/gtm/gate.py` or
  `factory/gtm/doctor.py` yet — both currently source their checks from
  `docs/gtm/MISSION.md` and `harness/gtm/END-TO-END.md` only.
