---
name: retro
description: Look back at one session and propose changes to the agent's environment — navigation pointers, automated checks, review rules, steering files, tool economy, information access.
disable-model-invocation: true
argument-hint: "[session-id, default this session]"
---

# Retro

Find what in the **environment** made one session slower or more wrong than it had to be, and
propose the change that removes the cause. A finding is about the environment the agent ran in,
never about the code the session wrote. `usage-review` does this across weeks of sessions; this
skill does it for one, while the session is still fresh.

Adapted from Matt Pocock's `retro` (github.com/mattpocock/skills).

## Steps

1. **Trace the session.** The session is `$ARGUMENTS`, else this one (`${CLAUDE_SESSION_ID}`).

   ```bash
   python3 ~/.claude/skills/usage-review/scripts/session_trace.py <id> --subagents
   ```

   Read every prompt the human wrote. Done when you can list each place the human pushed or
   corrected, each place the agent went wrong, and each run of turns that bought nothing.

2. **Find the candidates.** Match each item from step 1 to a category below, and name its
   **mechanism**: the cause in the environment, as one line with the turn that shows it.

   - **Navigation**: the agent searched long for a file or a fact. The fix is a navigation
     pointer in the file the agent reads first.
   - **Automated checks**: the agent made a mistake that a lint rule, a type check or a test can
     catch. Read the repo's own checks first (`.pre-commit-config.yaml`, pixi or package tasks,
     the CI workflows): a check that exists but is unwired or broken is the finding. A repo with
     no **guardrail** (no hook and no CI job that runs its checks) is a finding by itself.
   - **Review rules**: the review missed a mistake. Classify it first (below).
   - **Steering files**: a `CLAUDE.md`, `AGENTS.md` or memory line that did not change what the
     agent did, or that a check can replace. Judge it with the verdicts in
     [instruction-audit.md](../usage-review/references/instruction-audit.md).
   - **Skills**: a skill that did not load, loaded for the wrong case, or whose step the agent
     cut short. The fix is in its description or in that step's completion criterion.
   - **Tool economy**: an expensive call: a whole file, log or diff in the parent context, a
     poll loop, a fix-and-retry loop that belonged in a subagent.
   - **Information access**: a fact the agent needed was out of reach: a log, CI output, a
     container's state, a third-party service. The fix gives read access.

3. **Classify each review finding.** A **mechanical** mistake (a fixed pattern, a banned API, an
   import shape, a file location) gets a deterministic check: a lint rule, a prek hook or a CI
   job, whichever the repo's guardrail makes cheapest. A **judgement call** gets a rule for the
   reviewer. The reviewer reads a diff and has context to spare; the implementer has the least.
   So a judgement rule goes where the reviewer reads it, and `CLAUDE.md` holds navigation
   pointers only.

4. **Report.** List the findings, the most severe first. Each one gives the turn that shows it,
   the mechanism, the change, and the file to change (a repo file, a skill or `CLAUDE.md` in the
   chezmoi source, a hook, a setting, a memory). Done when every item from step 1 has a finding
   or a stated reason to leave it.

   Offer to apply the changes; edit only when the human says yes. A change to a team repo is a
   proposed PR. When a change moves a metric that `usage-review` measures, offer to add it to the
   ledger as an experiment.
