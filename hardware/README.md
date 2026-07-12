# 3D-Printable Case

A parametric enclosure for the **Raspberry Pi 5 + 5" HDMI display + ReSpeaker**.

## Files
- `case.scad` — the editable source model (OpenSCAD).

## How to get a printable STL
1. Install **OpenSCAD** (free): https://openscad.org
2. Open `case.scad`.
3. **Measure your actual hardware with calipers** and update the numbers in the
   `USER DIMENSIONS` block. The defaults are typical for a Waveshare-style 5"
   HDMI LCD, a Pi 5, and a round ReSpeaker USB array — but a good fit needs
   *your* real measurements (display board size, screen opening, mic diameter,
   and where the Pi's ports land).
4. Set `PART = "back";` → press **F6** → **File → Export → Export as STL**.
5. Set `PART = "bezel";` → **F6** → export the second STL.
6. Print both parts.

## Print settings
- **Material:** PLA or PETG
- **Layers:** 0.2 mm
- **Walls:** 3 perimeters
- **Infill:** 15–20%
- **Back shell:** print open-face down — no supports needed
- **Bezel:** print face-down; the screw/retaining posts may want light supports

## Assembly
1. Screw the Pi 5 onto the four standoffs in the back shell (M2.5 screws).
2. Seat the ReSpeaker into the round recess behind the top grille.
3. Drop the 5" display into the bezel's inner ledge (glass facing out).
4. Connect HDMI + USB between the display and the Pi, and the ReSpeaker USB.
5. Close the bezel onto the back shell. Add M3 screws or a bead of hot glue at
   the corners to hold it shut (add corner screw holes in the SCAD if you want
   a fully screwed case).

## Important
This is a **starting-point design** — the port cutouts and sizes almost
certainly need one test print + small tweaks to fit your exact boards. Print
the back shell first, check the Pi and port alignment, adjust the numbers, and
reprint. Increase `tol` if parts fit too tightly.
