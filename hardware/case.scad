// ============================================================================
//  AI Lecture Note-Taker — enclosure for Raspberry Pi 5 + 5" HDMI display
//  + ReSpeaker mic.  Parametric OpenSCAD model.
//
//  HOW TO USE
//    1. Install OpenSCAD (free): https://openscad.org
//    2. Open this file.
//    3. MEASURE your actual boards with calipers and update the numbers in the
//       "USER DIMENSIONS" block below — the defaults are typical but yours may
//       differ by a few mm, and a good fit needs real measurements.
//    4. Set PART = "back" (or "bezel"), press F6 to render, then
//       File > Export > Export as STL.  Print each part separately.
//
//  PRINTING
//    - PLA or PETG, 0.2 mm layers, 3 walls, 15-20% infill.
//    - Back shell: print open-face-down (no supports needed).
//    - Bezel: print face-down; screw posts may want light supports.
// ============================================================================

// Which part to render/export: "back", "bezel", or "both" (preview only).
PART = "both";

$fn = 48;                 // curve smoothness

// ---------------------------------------------------------------------------
//  USER DIMENSIONS  — MEASURE YOUR HARDWARE AND EDIT THESE
// ---------------------------------------------------------------------------

// ---- 5" display board (the whole PCB, not just the glass) ----
disp_w        = 121;      // display board width  (mm)
disp_h        = 78;       // display board height (mm)
disp_thick    = 4;        // display board thickness incl. components behind glass

// Visible/active screen area (the hole the bezel opens over), centered.
screen_w      = 110;      // visible width  (mm)
screen_h      = 62;       // visible height (mm)
screen_off_x  = 0;        // shift screen opening left/right if not centered
screen_off_y  = 0;        // shift screen opening up/down if not centered

// ---- Raspberry Pi 5 ----
pi_w          = 85;       // Pi 5 length (mm)
pi_h          = 56;       // Pi 5 width  (mm)
pi_hole_dx    = 58;       // mounting hole spacing (long axis)
pi_hole_dy    = 49;       // mounting hole spacing (short axis)
pi_hole_inset = 3.5;      // holes are 3.5 mm in from the board edges
pi_standoff_h = 6;        // how far the Pi floats off the back wall
pi_screw_d    = 2.5;      // M2.5 screws into the standoffs

// ---- ReSpeaker mic ----
// Round USB array style. For a rectangular HAT, use a rect recess instead.
mic_dia       = 70;       // ReSpeaker board diameter (mm) — measure yours
mic_recess_h  = 3;        // depth of the recess it sits in
mic_grille_n  = 5;        // rings of holes in the mic grille
mic_hole_d    = 3;        // diameter of each grille hole

// ---- Case build parameters ----
wall          = 3;        // wall thickness
tol           = 0.4;      // fit tolerance (increase if parts are too tight)
inner_margin  = 3;        // gap around the display inside the case
case_depth    = 24;       // internal depth (must fit Pi 5 + standoffs + display)
bezel_lip     = 4;        // how far the bezel overlaps the screen edge
corner_r      = 4;        // outside corner rounding

// Derived overall inner cavity size (based on the display footprint).
inner_w = disp_w + 2*inner_margin;
inner_h = disp_h + 2*inner_margin;
outer_w = inner_w + 2*wall;
outer_h = inner_h + 2*wall;

// ---------------------------------------------------------------------------
//  HELPERS
// ---------------------------------------------------------------------------

// Rounded rectangular prism.
module rrect(w, h, d, r) {
    hull() for (x = [-1, 1], y = [-1, 1])
        translate([x*(w/2 - r), y*(h/2 - r), 0])
            cylinder(h = d, r = r);
}

// A single Pi standoff with a pilot hole.
module standoff(h, outer_d, hole_d) {
    difference() {
        cylinder(h = h, d = outer_d);
        translate([0, 0, 1]) cylinder(h = h, d = hole_d);
    }
}

// ---------------------------------------------------------------------------
//  BACK SHELL  — holds the Pi 5, has port cutouts + mic grille
// ---------------------------------------------------------------------------
module back_shell() {
    difference() {
        union() {
            // Outer box, open toward the front (+Z).
            difference() {
                translate([-outer_w/2, -outer_h/2, 0])
                    minkowski() {
                        cube([outer_w - 2*corner_r, outer_h - 2*corner_r, case_depth + wall]);
                        cylinder(r = corner_r, h = 0.01);
                    }
                // Hollow out the cavity.
                translate([-inner_w/2, -inner_h/2, wall])
                    cube([inner_w, inner_h, case_depth + wall]);
            }

            // Pi 5 mounting standoffs (centered on the back wall).
            translate([0, 0, wall])
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                    standoff(pi_standoff_h, 6, pi_screw_d);
        }

        // ---- Port cutouts (edit positions to match your Pi orientation) ----
        // Right wall: USB-C power + micro-HDMI + USB.  These are generous slots;
        // tighten to your layout after a test print.
        // USB-C power
        translate([outer_w/2 - wall - 1, -10, wall + 2])
            cube([wall + 4, 12, 8]);
        // HDMI / USB group
        translate([outer_w/2 - wall - 1, 6, wall + 2])
            cube([wall + 4, 26, 10]);

        // Left wall: USB-A ports for the ReSpeaker / keyboard.
        translate([-outer_w/2 - 3, -18, wall + 2])
            cube([wall + 4, 34, 12]);

        // Bottom wall: cable exit slot.
        translate([-14, -outer_h/2 - 3, wall + 2])
            cube([28, wall + 4, 10]);

        // ---- Mic grille + recess on the TOP wall ----
        translate([0, outer_h/2 - wall/2, case_depth/2 + wall])
            rotate([90, 0, 0])
                mic_grille();

        // Ventilation slots on the back wall.
        for (i = [-2:2])
            translate([i*10, 0, -0.5])
                cube([4, inner_h*0.5, wall + 1], center = true);
    }
}

// Mic grille: a shallow recess ringed with holes (drawn in local XY).
module mic_grille() {
    // Recess for the board.
    translate([0, 0, -mic_recess_h])
        cylinder(h = mic_recess_h + wall + 1, d = mic_dia + tol);
    // Ring of sound holes.
    for (ring = [1:mic_grille_n])
        for (a = [0 : 360/(ring*6) : 359])
            rotate([0, 0, a])
                translate([ring*(mic_dia/2/(mic_grille_n+1)), 0, -1])
                    cylinder(h = wall + 2, d = mic_hole_d);
}

// ---------------------------------------------------------------------------
//  FRONT BEZEL  — frames the screen, holds the display board in
// ---------------------------------------------------------------------------
module front_bezel() {
    difference() {
        // Bezel plate matching the case outline.
        translate([0, 0, 0])
            rrect(outer_w, outer_h, wall, corner_r);

        // Screen opening (slightly smaller than the visible area = lip).
        translate([screen_off_x, screen_off_y, -1])
            rrect(screen_w - 2*bezel_lip, screen_h - 2*bezel_lip, wall + 2, 2);
    }

    // Inner ledge that the display board rests against + retaining wall.
    translate([0, 0, wall])
    difference() {
        rrect(disp_w + 2*tol + 2*2, disp_h + 2*tol + 2*2, disp_thick + 1, 2);
        translate([0, 0, -1])
            rrect(disp_w + 2*tol, disp_h + 2*tol, disp_thick + 3, 1);
        // Re-open the screen area through the ledge.
        translate([screen_off_x, screen_off_y, -1])
            cube([screen_w, screen_h, disp_thick + 4], center = true);
    }
}

// ---------------------------------------------------------------------------
//  RENDER
// ---------------------------------------------------------------------------
if (PART == "back")  back_shell();
else if (PART == "bezel") front_bezel();
else {
    // Preview both, bezel flipped and offset so you can see the pair.
    back_shell();
    translate([outer_w + 20, 0, 0]) front_bezel();
}
