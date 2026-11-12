---
name: rerun-to-artifact
description: Put the 3-D views of a rerun recording (robot, sensors, scene, what a benchmark marks) into a standalone claude.ai artifact that people off the internal network can open. Use when a share page needs the 3-D views of a rerun or bencher report, or when an artifact's rerun view shows nothing.
---

# Rerun views in a standalone artifact

An artifact cannot run the rerun web viewer:
- Its CSP admits scripts only from cdnjs, jsdelivr `/npm/` and unpkg, and allows no fetch to other hosts.
- The viewer needs a ~54 MB wasm file.
- The `.rrd` file sits on an internal host.

So **rebuild** the views instead. Export the geometry with the benchmark's own code, and draw it with three.js in the page. The rebuild is done when the page shows the same things as the rerun view, its numbers match the report, and it loads with no errors.

A worked example is in `~/.claude/handoffs/rerun-to-artifact-example/`, when that folder exists: `export_views.py`, `run.sh`, `stubs.py` and `page.html`. It holds company code, so it stays out of this public repo. Read it before you start.

## Steps

1. **Find what the view draws.** Read the function that logs to rerun (for example `_render_rerun`). That function is the source of truth, not the `.rrd` file. Use `rerun rrd print -vvv` on the `.rrd` only to confirm the list of entities.

2. **Export at the exact commit of the shared result.**
   - Make a git worktree at that commit inside the project's container.
   - Subclass the benchmark, and override the render hook so that it *captures* what it would log. Run the benchmark's own scoring; do not write your own.
   - If the container's build is gone, put the worktree's packages first on `PYTHONPATH`, and stub the imports that are never called (see the example `run.sh` and `stubs.py`). Print the module path and the commit in the log.
   - **Done when** the metrics computed from the captured data match the report. Say how big any difference is.

3. **Pack the data small.** Keep the total ≤ ~12 MB and each file < 10 MB.
   - Meshes: decimate each part (`trimesh` `simplify_quadric_decimation`, ~60k triangles per pose). Store positions as int16 at 0.1 mm, and indices as uint32.
   - Voxel and cell masks: `np.packbits(..., bitorder="little")` over one shared index.
   - Metadata, transforms and small shapes go in one `index.json`.

4. **Encode the binary files as text.** Artifacts serve no `.bin` file, and no `application/octet-stream` file. Write each file as base64 in a `.b64.txt` file. In the page, decode it with `atob` into a `Uint8Array`. Check the round trip before you publish.

5. **Write the viewer.**
   - Use an importmap: `three` → `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js`, and `three/addons/` → `.../examples/jsm/`. Use `OrbitControls` from the addons.
   - Fetch the data with relative paths (`data/...`). Set `camera.up` to z.
   - Take every colour from the page's CSS tokens. Apply the colours again on a theme change (a `prefers-color-scheme` listener and a `data-theme` observer).
   - Draw the robot opaque. Draw the scene objects see-through: opacity ~0.25, `depthWrite: false`, plus edge lines. Opaque boxes hide the robot.
   - Add selectors for the variants (rig, pose, scene), toggles for each layer, and a readout of the metrics. Resize with a `ResizeObserver`.

6. **Check it in a browser.**
   - Serve the folder with `python3 -m http.server` on a free localhost port. Record the pid, and kill only that pid.
   - Render with playwright-core and Chromium, started with `--use-angle=swiftshader`. Take screenshots at 1400 px and 400 px, in light and dark. Look at them.
   - **Done when** there is no `pageerror` and no failed data request. A local server sends no charset, so `°` and `²` can show as mojibake there; the publish skeleton fixes that.

7. **Publish.** Publish with `file_path` = the page, `root` = its folder, and every data file listed in `files`.
   - The page is private. Tell the user to share it from the page's Share menu.
   - When the claude.ai account rotates, an update can fail with "artifact deleted". Then publish again to a new URL, and tell the user that the old link is dead.
