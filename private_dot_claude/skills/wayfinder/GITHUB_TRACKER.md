# Wayfinding operations — GitHub Issues via `gh`

How this tracker expresses the map, child tickets, claiming, blocking, and the frontier. All commands run in the repo's working directory; resolve `OWNER/REPO` once with:

```bash
gh repo view --json nameWithOwner --jq .nameWithOwner
```

**Two kinds of id.** `gh issue` subcommands take the issue **number** (`#42`). The sub-issue and dependency REST endpoints take the numeric **database id** in the body. Convert on demand:

```bash
gh api repos/OWNER/REPO/issues/NUMBER --jq .id
```

## Labels (once per repo, idempotent)

```bash
for l in map research prototype grilling task; do
  gh label create "wayfinder:$l" --color 1D76DB 2>/dev/null || true
done
```

## Create the map

```bash
gh issue create --title "<map name>" --label wayfinder:map --body-file map.md
```

Update the body later (Decisions so far, fog graduation) with `gh issue edit MAP_NUMBER --body-file map.md`. Read-modify-write: fetch the current body first (`gh issue view MAP_NUMBER --json body --jq .body`), edit, write back — other sessions may have appended since you loaded it.

## Create a ticket (create, then parent)

Issues need ids before they can reference each other, so this is always two steps:

```bash
gh issue create --title "<ticket name>" --label wayfinder:grilling --body-file ticket.md
TICKET_ID=$(gh api repos/OWNER/REPO/issues/TICKET_NUMBER --jq .id)
gh api -X POST repos/OWNER/REPO/issues/MAP_NUMBER/sub_issues -F sub_issue_id="$TICKET_ID"
```

List a map's children: `gh api repos/OWNER/REPO/issues/MAP_NUMBER/sub_issues`

## Blocking (native dependencies)

To record "ticket B is blocked by ticket A" (`issue_id` is A's **database id**):

```bash
gh api -X POST repos/OWNER/REPO/issues/B_NUMBER/dependencies/blocked_by -F issue_id="$A_ID"
```

Inspect: `gh api repos/OWNER/REPO/issues/B_NUMBER/dependencies/blocked_by` (and `/blocking` for the reverse edge). Remove: `gh api -X DELETE repos/OWNER/REPO/issues/B_NUMBER/dependencies/blocked_by/$A_ID`. GitHub renders these relationships in the issue UI, so the human sees the frontier without opening the map.

## Claim a ticket

```bash
gh issue edit TICKET_NUMBER --add-assignee @me
```

An open, unassigned ticket is unclaimed. Claim **before any work**.

## Frontier query

Open, unblocked, unclaimed children of the map:

```bash
gh api repos/OWNER/REPO/issues/MAP_NUMBER/sub_issues --paginate \
  --jq '.[] | select(.state == "open" and (.assignees | length == 0)) | .number' |
while read -r n; do
  open_blockers=$(gh api "repos/OWNER/REPO/issues/$n/dependencies/blocked_by" \
    --jq '[.[] | select(.state == "open")] | length')
  [ "$open_blockers" -eq 0 ] && echo "$n"
done
```

## Resolve a ticket

```bash
gh issue comment TICKET_NUMBER --body-file resolution.md   # the answer lives here
gh issue close TICKET_NUMBER
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
