# Current ensemble-product review continuation

This schema-4 audit copy continues `stage1.1-i06-current-member-accumulation/review-schema4.db`. It preserves every existing table row, all 189 mappings, and 223 active parameters. No formal ensemble definition or mapping was added: current inspected files and declarations do not establish a published mean/spread product and its population/method.

GEPS/REPS dependency-closed exports remain content version 2 and match the predecessor byte for byte. `derivation.json`, `mapping-diff.json`, and `migration-report.json` record the unchanged resources; `formal-product-review.json` records four candidate reviews without creating migration identities or changing the existing 435 unresolved obligations.

The inherited `new-definitions-review.json` describes the three accumulation variants reviewed in the preceding batch, not new definitions in this batch. The legacy review remains 125 resolved and 96 evidence-dependent definitions, with 429 legacy obligations and six separate accumulation-variant backend coverage obligations.

Workspace evidence is under `doc/2026-10-13-stage1.1-query-reki/evidence/I03/round-10`, `I04/round-11`, and `I06/round-14`. The continuation generator is `I03/round-10/prepare_review.py`; it uses a fixed 189-row predecessor and requires a new destination. Adjust inputs and outputs before the next batch, preserve all prior audit copies, and do not treat controlled runtime tests as operational product support.
