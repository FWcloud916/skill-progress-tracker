# Known Issues

> **Last updated:** 2026-07-26

## KI-001 — Migration can miss actionable content outside the explicit WIP section

**Status:** Open  
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

