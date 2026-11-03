Read the talk "{title}" from the files the earlier steps wrote. Do not use WebFetch on the
YouTube page: it returns the player shell, and a summary built from it is invented.

- Metadata and chapters: {meta_path}
- Transcript ({transcript_source}, {transcript_lines} lines): {transcript_path}
- Slides, one PNG per slide change, named mm-ss: {slides_dir}
- Links decoded from QR codes: {qr_links}

Do this:

1. Read the metadata. The chapters are the outline: {chapters}
2. Read the whole transcript. Auto-captions and Whisper mishear names ("Neo forj" for
   Neo4j, "Langraph" for LangGraph). Fix each name from the slides and the description,
   never by guessing, and list each fix.
3. Look at the slide at each chapter start and the last few slides, `zz-end.png` included.
   Resource slides print the URL under each QR code, so read them even when the QR list
   above is empty. Copy every URL, repo, paper id and product name you see.
4. Write `notes.md` in the work directory: per chapter, the claims with `[mm:ss]`, then
   the slide content the speaker only points at, then the demo steps.

Produce:
- `notes_path`: the absolute path of `notes.md`.
- `slide_links`: every URL printed on a slide, as strings, the QR ones included. Write a
  paper id as its URL (arXiv 2606.04781 -> https://arxiv.org/abs/2606.04781).
- `name_fixes`: each fix as "heard -> correct". A name that no slide or the description
  confirms stays as heard; list it in the notes under "Not confirmed".
