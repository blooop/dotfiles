"""qr-links: decode QR codes on the slides (upscaled; slide QR codes are small)."""
import os

from talklib import HERE, emit, read_state, run

state = read_state()
r = run(["uvx", "--with", "opencv-python-headless", "python", "-I", os.path.join(HERE, "qr.py"),
         *state["slide_paths"]], check=False)
links = []
for line in r.stdout.splitlines():
    frame, _, url = line.partition(" ")
    links.append({"url": url, "slide": frame})
emit({"qr_links": links})
