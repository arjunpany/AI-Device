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

## Two parts
- **base** — the tray: floor, walls, Pi standoffs, and the port cutouts.
- **lid** — the top: holds the screen and the ReSpeaker (both facing up) and
  lifts off for wiring.

## Assembly
1. **Screw the Pi onto the standoffs** in the base tray.
2. **Fit the 5" display into the lid** — it drops into the pocket from below,
   screen facing up through the opening; screw it to the four posts.
3. **Rest the ReSpeaker in the dish** on the lid; route its USB cable down
   through the hole into the box.
4. Run the display's HDMI/USB/power and the mic USB down into the base and plug
   them into the Pi. Route external cables (power, etc.) out through the wall
   **port cutouts** and grommet holes.
5. **Drop the lid onto the base.** The rim locates it; add a little tape or a
   couple of screws if you want it fixed.

## Fitting the ports
The wall openings are big and generous, but their positions (`right_port_*`,
`back_port_*`, `port_z`) still need to match where your Pi's ports actually sit.
Print the base first, set the Pi in place, see where the ports land, and nudge
those numbers before the final print.

## Important
This is a **starting-point design** — the port cutouts and sizes almost
certainly need one test print + small tweaks to fit your exact boards. Print
the back shell first, check the Pi and port alignment, adjust the numbers, and
reprint. Increase `tol` if parts fit too tightly.
