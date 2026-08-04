# Wayfinding operations — GitHub Issues via `gh`

How this tracker expresses the map, child tickets, claiming, blocking, and the frontier.

## Pin the repo first

Every command below targets `$REPO` **explicitly**. Never let `gh` resolve the target itself: `gh issue` and `gh label` pick their repo from ambient state — the cwd at the moment the command runs, a `gh repo set-default` choice, or the `gh-resolved` entry in `.git/config` — and in a fork they resolve through the repo network to the **parent**. A session that steps into a worktree, a vendored checkout, or a subagent's directory would then file tickets into a different repo than the one it is mapping. Resolve once from the working repo's own `origin`, and pass `--repo` on every call:

```bash
REPO=$(git remote get-url origin | sed -E 's#^(ssh://)?(git@github\.com[:/]|https://github\.com/)##; s#\.git$##')
gh repo view "$REPO" --json nameWithOwner,visibility --jq '"\(.nameWithOwner) \(.visibility)"'
```

Show that line to the human before the first write of a charting session and stop if it isn't the repo they meant — the map body carries the Destination and the whole fog sketch, so it is both the most revealing artifact in the flow and the first one created. If `origin` isn't a GitHub remote, use the local-markdown fallback at the bottom of this file rather than reaching for another repo.

When `visibility` is anything but `PUBLIC`, the map is confidential: see **Keep the map inside its repo** in [SKILL.md](SKILL.md).

**Two kinds of id.** `gh issue` subcommands take the issue **number** (`#42`). The sub-issue and dependency REST endpoints take the numeric **database id** in the body. Convert on demand:

```bash
gh api "repos/$REPO/issues/NUMBER" --jq .id
```

## Labels (once per repo, idempotent)

```bash
for l in map research prototype grilling task; do
  gh label create "wayfinder:$l" --repo "$REPO" --color 1D76DB 2>/dev/null || true
done
```

## Create the map

```bash
gh issue create --repo "$REPO" --title "<map name>" --label wayfinder:map --body-file map.md
```

Update the body later (Decisions so far, fog graduation) with `gh issue edit MAP_NUMBER --repo "$REPO" --body-file map.md`. Read-modify-write: fetch the current body first (`gh issue view MAP_NUMBER --repo "$REPO" --json body --jq .body`), edit, write back — other sessions may have appended since you loaded it.

## Create a ticket (create, then parent)

Issues need ids before they can reference each other, so this is always two steps:

```bash
gh issue create --repo "$REPO" --title "<ticket name>" --label wayfinder:grilling --body-file ticket.md
TICKET_ID=$(gh api "repos/$REPO/issues/TICKET_NUMBER" --jq .id)
gh api -X POST "repos/$REPO/issues/MAP_NUMBER/sub_issues" -F sub_issue_id="$TICKET_ID"
```

List a map's children: `gh api "repos/$REPO/issues/MAP_NUMBER/sub_issues"`

## Blocking (native dependencies)

To record "ticket B is blocked by ticket A" (`issue_id` is A's **database id**):

```bash
gh api -X POST "repos/$REPO/issues/B_NUMBER/dependencies/blocked_by" -F issue_id="$A_ID"
```

Inspect: `gh api "repos/$REPO/issues/B_NUMBER/dependencies/blocked_by"` (and `/blocking` for the reverse edge). Remove: `gh api -X DELETE "repos/$REPO/issues/B_NUMBER/dependencies/blocked_by/$A_ID"`. GitHub renders these relationships in the issue UI, so the human sees the frontier without opening the map.

## Claim a ticket

```bash
gh issue edit TICKET_NUMBER --repo "$REPO" --add-assignee @me
```

An open, unassigned ticket is unclaimed. Claim **before any work**.

## Frontier query

Open, unblocked, unclaimed children of the map:

```bash
gh api "repos/$REPO/issues/MAP_NUMBER/sub_issues" --paginate \
  --jq '.[] | select(.state == "open" and (.assignees | length == 0)) | .number' |
while read -r n; do
  open_blockers=$(gh api "repos/$REPO/issues/$n/dependencies/blocked_by" \
    --jq '[.[] | select(.state == "open")] | length')
  [ "$open_blockers" -eq 0 ] && echo "$n"
done
```

## Resolve a ticket

```bash
gh issue comment TICKET_NUMBER --repo "$REPO" --body-file resolution.md   # the answer lives here
gh issue close TICKET_NUMBER --repo "$REPO"
# then append the context pointer to the map's Decisions so far (see map edit above)
```

## Local-markdown fallback

Only when the repo has no GitHub remote or issues are disabled. Everything lives in-repo and is committed, so collaborators share it through git:

- **Map**: `.wayfinder/map.md` — same body format as the issue map.
- **Tickets**: `.wayfinder/tickets/<slug>.md` — the `## Question` body, plus a metadata header:

  ```markdown
  - Type: grilling | research | prototype | task
  - Status: open | closed
  - Claimed by: <name, or blank>
  - Blocked by: [<ticket name>](<slug>.md), ...
  ```

- **Claiming** = writing your name to `Claimed by` and committing. **Blocking** = the `Blocked by` list (this tracker has no native blocking, so the body convention applies). **Frontier** = open tickets with empty `Claimed by` whose `Blocked by` entries are all `Status: closed`. **Resolution** = an `## Answer` section appended to the ticket, `Status: closed`, and a Decisions-so-far line in the map.
