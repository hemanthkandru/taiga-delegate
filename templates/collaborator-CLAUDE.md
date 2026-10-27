# Taiga tracking — delegated epic (always on)

> Give this file to a collaborator working with a **scoped token**. Fill in the
> epic ref/name, internal epic_id, and project_id, then have them drop it into
> their working directory as `CLAUDE.md` (or merge it into an existing one).

I track all development work in Taiga automatically via the `taiga` MCP server — no one should have to ask. My access is scoped to **epic #<ref> "<epic name>"** (internal epic_id <ID>) in the **<project>** project (project_id <N>). Everything I create lands under this epic automatically — I never need to pick a project or epic.

At the START of any substantive task, create the tracking BEFORE writing code:

**Feature / enhancement work:**
- Create a user story (`taiga_create_user_story`) with a clear subject and acceptance criteria as a markdown checklist. Multi-part work → several stories (`taiga_bulk_create_stories`).
- Set it "In progress" (`taiga_update_user_story`) when starting.
- When finished: ONE call — `taiga_update_user_story` with status "Done" + `comment` (files changed, test results). No mid-story comments unless blocked or scope changes.

**Bug found or fixed:**
- Create an issue (`taiga_create_issue`, type "Bug") with root-cause notes and a "## Test Cases" checklist.
- After fixing (tests written first, failing → passing): ONE call — `taiga_update_issue` with status "Closed" + `comment` summarizing the fix.

**No tracking needed:** pure questions, explanations, code reading.

Rules:
- To read the epic: `taiga_get_epic` with epic_id <ID>. To list its stories: `taiga_list_user_stories` with project_id <N> (the scope filters to the epic automatically).
- Comments are concise (≤3 sentences + file paths/test results); the detailed narrative belongs in git commits. Prefer the `comment` param on update calls over separate `taiga_add_comment` calls.
- Trust mutation results (`created`/`updated`) — don't re-list to confirm.
- My token cannot delete anything, edit the epic itself, or see other epics/projects. If a tool call is denied with a scope message, that's by design — don't retry or work around it; tell the user if it seems to block legitimate work.
- If the taiga MCP is unavailable, do the code work anyway and say tracking was skipped.
