"""qr.py PNG... — print "<frame> <url>" for each new QR code; upscales, since slide QRs are small."""
import sys

import cv2

det = cv2.QRCodeDetector()
seen = set()
for path in sys.argv[1:]:
    img = cv2.imread(path)
    if img is None:
        continue
    for scale in (1, 2, 3):
        im = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale > 1 else img
        ok, texts, _, _ = det.detectAndDecodeMulti(im)
        for t in texts if ok else []:
            if t and t not in seen:
                seen.add(t)
                print(path.rsplit("/", 1)[-1], t)
