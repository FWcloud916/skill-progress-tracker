# Known Issues

> **Last updated:** 2026-07-27

## KI-002 — Migration gate lacks durable destination and deletion evidence

**Status:** Resolved (2026-07-27)

**Detected:** 2026-07-27 during the clean-state follow-up trial against
`FWcloud916.github.io`

**Data loss:** None; the legacy source remains present and byte-identical

### Incident

The hardened whole-document scanner found all active content in the legacy
root `PROGRESS.md`, and `migration-audit` correctly held the deletion gate
closed until every blocking row had a disposition. After all 33 blocking rows
were marked `migrated`, the gate opened and disclosed two historical sections.

The resulting record was still weaker than its output implied:

1. A historical section was compressed to one row containing only its heading,
   so the record named `Done` and `Decision log` without preserving the entries
   that deletion would remove.
2. A `migrated` row proved only that its destination item slug existed; it did
   not carry a locator proving where that specific source entry landed.
3. The user's later retain/delete choice existed only in the conversation and
   final report, not in the durable migration record.

### Root cause

The KI-001 fix made source inventory completeness deterministic but left three
parts of the deletion decision as global human attestations: historical-detail
disclosure, per-row destination coverage, and the final source outcome. That
boundary is documented as an honest limit, but the command still prints
`Deletion gate: OPEN`, which can be read as stronger evidence than the record
actually contains.

### Impact

An agent can accidentally omit one destination entry, disclose only a
historical section name rather than its contents, or delete a source without
leaving durable proof of the user's decision. The source inventory remains
complete, but a later reviewer cannot reconstruct the full deletion basis from
the repository alone.

### Current workaround

- Keep the legacy source; do not act on the current open deletion gate.
- Manually compare every migrated record row with its destination item.
- Inspect the full contents of every historical/reference section before any
  deletion decision.
- Record any retain/delete decision outside the generated record until the
  finalization workflow exists.

### Required resolution

1. Inventory every historical entry instead of compressing a section to its
   title; keep those rows non-blocking by default.
2. Add per-row destination Evidence for `migrated` rows and verify that the
   locator exists uniquely in the destination item.
3. Add a durable, non-destructive finalization state machine:
   `pending → retained` or `pending → delete-approved → deleted`.
4. Support refreshing an existing v1 record into schema v2 without losing
   valid Disposition/Destination values, while resetting stale sign-offs.
5. Add unit and end-to-end regression coverage for historical detail,
   Evidence validation, source-retention decisions, and deletion confirmation.

### Resolution acceptance criteria

- The record contains each historical entry that would disappear with the
  source, and audit output groups those entries by section with counts.
- Every `migrated` row has a non-trivial, uniquely matching Evidence locator in
  its destination item.
- The script never deletes source files, but it records `retained`,
  `delete-approved`, and `deleted` transitions with dates and exact sources.
- `deleted` cannot be recorded while any approved source still exists, and
  deletion cannot be approved until the normal migration audit passes.
- Refreshing a v1 record produces schema v2, preserves compatible row choices,
  and resets every global sign-off.

### Resolution

Resolved in plugin version 1.6.0 with migration schema v2:

- Historical sections emit one record row per entry rather than one row per
  heading.
- Every `migrated` row requires a non-trivial, row-specific Evidence locator
  that occurs exactly once in its destination item and is not shared with
  another row.
- `migration-finalize` persists `retained`, `delete-approved`, and `deleted`
  outcomes. Delete approval seals the exact sources and a SHA-256 fingerprint;
  the script never deletes source files itself.
- Schema v1 refresh preserves compatible Disposition/Destination values,
  introduces unresolved Evidence for migrated rows, and resets sign-offs.

The clean-state acceptance trial against `FWcloud916.github.io` first restored
all prior trial changes, then inventoried 58 source entries. It reconciled all
33 actionable/ambiguous rows with unique destination Evidence and disclosed 24
historical entries (16 Done, 8 Decision log). The root `PROGRESS.md` and its
versioned snapshot had identical SHA-256 digests. After explicit user approval,
the workflow recorded `pending → delete-approved`, removed only `PROGRESS.md`,
passed tracker, pointer, and 32-link audits, and recorded
`delete-approved → deleted` with the approval fingerprint unchanged.

---

## KI-001 — Migration can miss actionable content outside the explicit WIP section

**Status:** Resolved (2026-07-26) — see `docs/design-decisions.md` §"Script-gate
migration inventory completeness (KI-001)"  
**Detected:** 2026-07-26 during a real migration trial against
`FWcloud916.github.io`  
**Data loss:** None; the legacy source was not deleted

### Incident

The legacy root `PROGRESS.md` said `Nothing in progress` under its `## Now`
section. The migration therefore treated the active-content set as empty,
updated project pointers to the new `progress/` tracker, reported that the
two-sided audit passed, and reached the prompt asking whether to delete the
legacy source.

That conclusion was wrong. The same source document still contained actionable
content under `## Next steps` and an SEO/AI-SEO backlog. Those entries were
unfinished tasks and next actions under the skill's own migration contract, so
the content audit should have failed and the deletion gate should not have been
reached.

### Root cause

The migration interpreted **in-progress content** too narrowly:

1. It used the explicit `## Now` status as the authoritative boundary instead
   of semantically inventorying the entire source document.
2. It equated “no active WIP item” with “no actionable content,” overlooking
   pending work stored under differently named sections.
3. The source-to-destination comparison only checked fields already selected
   for mapping; it did not prove that the source inventory itself was complete.
4. A successful tracker-structure and pointer audit created false confidence,
   even though those checks cannot detect omitted source content.

### Impact

If the user had approved deletion, the unmigrated Next steps and backlog could
have been lost along with the legacy file. Historical sections such as Feature
list, Done, and Decision log also require an explicit archive-or-delete choice,
even when they are not part of active-content migration.

### Current workaround

Before migrating, inventory every source section and classify it as:

- active/actionable;
- historical/reference; or
- ambiguous, requiring user confirmation.

Search for actionable signals across the whole document, including unchecked
tasks, Next steps, backlog, TODO, planned/not-started work, blockers, and
follow-ups. Do not infer an empty actionable set from a single status field or
section.

The deletion gate MUST remain closed while any actionable or ambiguous source
entry lacks either a destination or an explicit user-approved exclusion.

### Required resolution

Strengthen the migration workflow so its comparison proves **inventory
completeness**, not only equivalence of already mapped fields:

1. Produce a section-by-section source inventory before creating the mapping.
2. Give every actionable entry a stable comparison row and destination.
3. Reconcile the count and identity of actionable source entries against the
   destination items.
4. Treat ambiguous entries as blocking until the user classifies them.
5. Report historical/reference content that would be lost before asking to
   delete the source.
6. Add an evaluation case where `Now` is empty but `Next steps` or a backlog
   still contains pending work.

### Resolution acceptance criteria

- An empty WIP section cannot make the migration audit pass when actionable
  content exists elsewhere in the source.
- Every actionable source entry is migrated or explicitly excluded by the
  user.
- Historical/reference sections are disclosed before deletion.
- The deletion question is asked only after content-completeness, semantic,
  tracker-consistency, pointer, and link audits all pass.

### Resolution

Fixed by the `migration-inventory` and `migration-audit` subcommands plus the
follow-up hardening after a real-project review exposed incomplete Markdown
block extraction and an impossible deletion-signoff sequence. Full design
rationale: `docs/design-decisions.md` §"Script-gate migration inventory
completeness (KI-001)". Mapping to the items above:

| Required resolution | How it's satisfied |
|---|---|
| 1. Section-by-section source inventory before mapping | `migration-inventory` scans the whole document via `scan_source()`; prose, lists, and complete table rows become source-ordered rows in `<tracker-dir>/_migrations/<slug>.md` before any destination is chosen |
| 2. Stable comparison row + destination per actionable entry | Each entry gets a content-derived opaque ID (`entry_identity()`) stable across reformatting, with `Disposition`/`Destination` cells |
| 3. Reconcile count/identity of actionable entries against destinations | `migration-audit`'s `reconcile()` reports unaccounted/stale rows, compares every generated field except informational `Loc`, and requires a `migrated` Destination to be an existing tracker item slug |
| 4. Ambiguous entries block until classified | Any heading matching neither `ACTIONABLE_HEADINGS` nor `HISTORICAL_HEADINGS` is `ambiguous`, which blocks identically to `actionable` (`BLOCKING_KINDS`) |
| 5. Report historical/reference content before deletion | `migration-audit` unconditionally prints every historical section, and a sign-off box attests it was shown to the user |
| 6. Eval case: `Now` empty, `Next steps`/backlog pending | `evals/scenarios/migration-gate-blocks-empty-now/` reproduces the exact incident shape and asserts the audit still fails; `evals/scenarios/migration-gate-opens-after-resolution/` is the resolved counterpart |

Acceptance criteria: the KI-001 regression scenario and
`test_fails_while_next_steps_unresolved_though_now_is_empty` in
`test_update_progress.py` both assert the empty-`## Now` case cannot pass;
`migration-audit` requires a `Disposition`/`Destination` per entry (not just
"migrated or excluded" as a checkbox, but a resolvable value); changed
inventories reset global sign-offs; historical
disclosure is unconditional on every run; and the deletion question is only
ever reached after `migration-audit` exits 0, which itself calls
`audit_tracker()` (tracker-consistency) and requires the pointer/link/semantic
sign-off boxes to be ticked. The later retention choice is not a pre-deletion
sign-off, and `migration-audit` is rerun immediately before an approved
deletion rather than after its source has disappeared.
