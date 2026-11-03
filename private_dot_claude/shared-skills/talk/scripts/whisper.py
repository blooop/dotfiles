"""whisper.py AUDIO OUT — transcribe to "[mm:ss] text" lines; GPU when there is one.

ctranslate2 dlopens cuBLAS/cuDNN at runtime, so the pip-installed NVIDIA libs must be on
LD_LIBRARY_PATH before the process starts: the script re-executes itself once with it set.
Audio is decoded by ffmpeg into an array, which avoids faster-whisper's PyAV path
(PyAV 15+ breaks it: "open() got an unexpected keyword argument 'metadata_errors'").
"""
import os
import shutil
import subprocess
import sys

if "WHISPER_LIBS_SET" not in os.environ:
    try:
        import nvidia.cublas
        import nvidia.cudnn

        libs = [os.path.join(p, "lib") for m in (nvidia.cublas, nvidia.cudnn) for p in m.__path__]
        os.environ["LD_LIBRARY_PATH"] = ":".join(libs + [os.environ.get("LD_LIBRARY_PATH", "")])
    except ImportError:
        pass
    os.environ["WHISPER_LIBS_SET"] = "1"
    os.execv(sys.executable, [sys.executable, "-I", *sys.argv])

import numpy as np
from faster_whisper import WhisperModel

audio_path, out_path = sys.argv[1], sys.argv[2]
gpu = shutil.which("nvidia-smi") is not None
model = WhisperModel(
    "large-v3" if gpu else "small.en",
    device="cuda" if gpu else "cpu",
    compute_type="float16" if gpu else "int8",
)
pcm = subprocess.run(
    ["ffmpeg", "-loglevel", "error", "-i", audio_path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
    capture_output=True,
    check=True,
).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
segments, _ = model.transcribe(audio, language="en", vad_filter=True)
with open(out_path, "w") as f:
    for s in segments:
        f.write(f"[{int(s.start // 60):02d}:{int(s.start % 60):02d}] {s.text.strip()}\n")
