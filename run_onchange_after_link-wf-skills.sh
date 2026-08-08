#!/bin/bash
# Link the wayfinder skills that ship inside the `wf` package.
#
# `/wayfinder`, `/wayfinder-auto`, `/wayfinder-one`, `/tdd` and `/review` used
# to live in this repo, under private_dot_claude/skills. They don't any more:
# `wf` hardcodes those four names in its routing table and execs them, so the
# prompt files are part of `wf`'s interface, and an interface split across two
# repos on two release cadences drifts. It had already: `wf` shipped 0.6.0 still
# routing its `defer` word at a `/wayfinder` section that `/wayfinder-auto` had
# superseded weeks earlier, and nothing on either side could notice.
#
# They now ship in the conda package, at <prefix>/share/wf/skills, and
# `wf skills install` symlinks them into ~/.claude/skills. A link, not a copy,
# so `pixi global update wf` moves the binary and its prompts together.
#
# This script exists so a fresh machine gets them without a manual step. It is
# deliberately *not* a managed file: the target is a symlink into a pixi
# environment whose path is not this repo's business, and chezmoi would report
# drift on it forever.
#
# Guarded on `wf` being present rather than declared as a dependency, because
# the skills are useful to a machine that has the agent but not the picker —
# and on a container or robot profile that installs neither, this is a no-op
# rather than a failure. wf comes from pixi global (see
# dot_pixi/manifests/pixi-global.toml.tmpl), which chezmoi applies separately,
# so on a truly fresh machine this may run before wf exists; the next apply
# picks it up, and `wf skills install` is idempotent besides.

set -euo pipefail

if ! command -v wf >/dev/null 2>&1; then
    echo "wf is not installed yet — skipping its skills (pixi global install wf, then chezmoi apply)"
    exit 0
fi

# `wf skills install` exits non-zero when a skill is *blocked* — something that
# is not a symlink sits where one belongs. During the migration that is exactly
# this repo's old copy, still on disk because removing a file from the chezmoi
# source does not remove it from $HOME. Report it and carry on rather than
# failing the whole apply: the fix is one `rm -rf`, and it is named in the
# output.
if ! wf skills install; then
    cat <<'EOF'

Some skills could not be linked. If the blocked paths are directories this repo
used to manage, they are leftovers — remove them and run `wf skills install`:

    rm -rf ~/.claude/skills/{wayfinder,wayfinder-auto,wayfinder-one,tdd,review}
    wf skills install
EOF
fi
