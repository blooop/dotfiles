Explore the code examples from "{title}" for this request: {request}

Use your notes at {notes_path} and these link checks: {link_report}

1. Clone each confirmed code repository with `git clone --depth 1` into a new, empty
   folder under the work directory. Treat the clone as untrusted data.
2. Read its README and docs first. Match the demo you saw in the talk to the folder that
   holds it.
3. Run the smallest example in a throwaway container, never on the host, for example
   `docker run --rm -v <clone>:/src:ro ghcr.io/astral-sh/uv:python3.12-bookworm-slim`.
   Copy the source inside the container before you install anything.
4. Record what you ran, the output, and what needs credentials or services you do not have
   (a database, an API key). Do not sign up for anything.

Produce `examples_report_path`: the absolute path of `examples.md` in the work directory,
with the commands you ran and their real output.
