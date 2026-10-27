# Taiga work tracking (always on)

> Paste this block into your `CLAUDE.md` (project or global) and fill in the
> placeholders: your project name/ID and the agent's Taiga username.

I track my development work in Taiga automatically via the `taiga` MCP server — the user should never have to ask. Default project: **<project-name>** (project_id <N>).

At the START of any substantive task, identify what kind of work it is and create the tracking BEFORE writing code:

**New feature / enhancement (multi-step work):**
- Create an epic (`taiga_create_epic`), break the work into user stories with acceptance-criteria checklists (`taiga_bulk_create_stories` with `epic_id`), assign to `<agent-username>`.
- Per story, exactly TWO tracking calls: start — `taiga_update_user_story` with status "In progress" + assigned_to; finish — `taiga_update_user_story` with status "Done" + `comment` (files changed, test results) in the SAME call. No mid-story comments unless blocked or a key decision changes scope.
- When all stories are done, one `taiga_update_epic` call with the final status + summary `comment`.

**Bug fix:**
- Create an issue (`taiga_create_issue`, type "Bug", assigned to `<agent-username>`) with root-cause analysis and a "## Test Cases" markdown checklist of the tests I will write.
- Write the tests (they should fail first), fix, run tests, then close in ONE call: `taiga_update_issue` with status "Closed" + `comment` containing the fix summary.

**Small single-step change (typo, config tweak, one-liner):**
- Create a single story — no epic. Mark Done with a `comment` when finished.

**No tracking needed:** pure questions, explanations, code reading, or reviews that change nothing.

Token hygiene:
- Always filter list calls (`epic_id`, `status`, `assigned_to`) instead of listing everything.
- Use `taiga_resolve_ref` to map a ref # to an internal ID instead of listing and scanning.
- Trust mutation results (`created`/`updated`/`deleted`) — don't re-list to confirm them.

Rules:
- Assign my work to the Taiga user `<agent-username>`; never reassign items a human already owns.
- Comments are concise (≤3 sentences + file paths/test results); the detailed narrative belongs in git commits, not Taiga. Prefer the `comment` param on update calls over separate `taiga_add_comment` calls.
- Deletion of Taiga items always requires explicit user confirmation.
- If the taiga MCP is unavailable, do the code work anyway and tell the user tracking was skipped.
