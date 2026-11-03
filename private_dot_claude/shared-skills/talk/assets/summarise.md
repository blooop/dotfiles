Write the summary of "{title}" that the user asked for: {request}

Use your notes at {notes_path} and these link checks: {link_report}

- Lead with the talk's main claim in two sentences.
- Then one short section per chapter. Cite each claim with `[mm:ss]` so the user can jump
  to it.
- Keep three things apart: what the speaker said, what the slides show, and your own view.
  Mark your own view as yours.
- List every link as a markdown link. Mark a link the check could not confirm as
  unconfirmed; never drop it in silence.
- The user reads this summary directly: write it in the voice their instructions set for
  chat messages.

Produce `summary_path`: the absolute path of `summary.md` in the work directory.
