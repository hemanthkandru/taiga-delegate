---
description: Implement a feature — create a Taiga epic + user stories, then work story by story
argument-hint: <description of the feature>
---

Implement the following feature, tracking it in Taiga as an epic with user stories: $ARGUMENTS

Follow this workflow strictly, in order:

## 1. Plan
- Explore the codebase to understand where the feature fits.
- Break the feature into 2–7 user stories. Each story must be independently implementable and testable, ordered by dependency.

## 2. Create the epic and stories in Taiga
- Resolve the project's numeric ID by calling `taiga_list_projects` and matching its slug (set your default project here). Use a different project only if I name one.
- Call `taiga_create_epic` with the feature name and a description covering the goal and the story breakdown.
- Create the user stories with `taiga_bulk_create_stories` (pass `epic_id` so they are linked automatically):
  - `subject`: story title
  - `description`: acceptance criteria as a markdown checklist
- Show me the epic + story list (refs/ids) before writing code. If I've already approved the plan in this conversation, proceed without waiting.

## 3. Work story by story
For each story, in dependency order:
1. Call `taiga_update_user_story` to set `status: "In progress"` and `assigned_to`: the AI agent's Taiga username (skip the assignment if the story already has a human assignee).
2. Implement the story. Match existing code conventions.
3. Write tests covering the story's acceptance criteria; run them plus the relevant existing suite — all must pass.
4. Call `taiga_update_user_story` to set `status: "Done"` (or the project's closest done-state) AND a `comment` summarizing what was implemented (files changed, tests added, results) — one call, not two.

Do not start a story until the previous one is done and its tests pass.

## 4. Close the loop
- After all stories are done, call `taiga_update_epic` to mark the epic completed (if the project has epic statuses) with a `comment` giving an overall summary.
- Give me a final summary: what was built, per-story status, tests, and the epic reference.

If any Taiga call fails, continue the implementation work and report the tracking failure at the end — never let tracking block the code.
