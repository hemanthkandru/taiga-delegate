---
description: Fix a bug end-to-end — track it as a Taiga issue, add test cases, resolve it
argument-hint: <description of the bug or unexpected behavior>
---

Fix the following bug, tracking it in Taiga throughout: $ARGUMENTS

Follow this workflow strictly, in order:

## 1. Identify
- Investigate the codebase to find the root cause. Reproduce the problem if possible.
- Do not write any fix yet.

## 2. Create the Taiga bug
- Resolve the project's numeric ID by calling `taiga_list_projects` and matching its slug (set your default project here). Use a different project only if I name one.
- Call `taiga_create_issue` with:
  - `issue_type`: "Bug"
  - `subject`: a one-line summary of the bug
  - `description`: root cause analysis (file/line references), reproduction steps, and a **Test Cases** section — a markdown checklist of the test cases you will implement, e.g.:
    ```
    ## Test Cases
    - [ ] returns 404 when the record does not exist
    - [ ] handles empty payload without crashing
    ```
  - `severity`/`priority` based on impact.
  - `assigned_to`: the AI agent's Taiga username, since the agent is doing the fix.
- Report the created issue ref/id to me.

## 3. Add test cases
- Write automated tests covering each item in the Test Cases checklist, using the repo's existing test framework and conventions.
- Run them and confirm they FAIL for the right reason (they reproduce the bug).

## 4. Resolve
- Implement the fix. Keep it minimal — no drive-by refactoring.
- Run the new tests plus the relevant existing suite; all must pass.

## 5. Close the loop in Taiga
- Call `taiga_update_issue` with `status: "Closed"` AND a `comment` summarizing the fix (files changed), the tests added, and test results — one call, not two. (If "Closed" doesn't exist in this project, use the project's closed-most status.)
- Give me a final summary: root cause, fix, tests, and the Taiga issue reference.

If any Taiga call fails, continue the code work and report the tracking failure at the end — never silently skip the fix.
