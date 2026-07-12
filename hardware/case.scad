// ============================================================================
//  AI Lecture Note-Taker — BIG enclosure
//    * Roomy box that houses the Raspberry Pi 5
//    * Front face with a screen opening + screw posts to SCREW the display in
//    * Flat top with a recess where the ReSpeaker RESTS on the surface
//    * Open back for easy wiring (optional screw-on back cover included)
//
//  HOW TO USE
//    1. Install OpenSCAD (free): https://openscad.org
//    2. Open this file.  MEASURE your boards and edit the USER DIMENSIONS.
//    3. Set PART = "case" -> press F6 -> File > Export > Export as STL.
//       (Optionally PART = "backcover" for a closing panel.)
//    4. Print.  PLA/PETG, 0.2 mm, 3 walls, 15-20% infill.
// ============================================================================

PART = "case";            // "case", "backcover", or "both" (preview)
$fn = 64;

// ---------------------------------------------------------------------------
//  USER DIMENSIONS — measure your hardware with calipers and edit these
// ---------------------------------------------------------------------------

// ---- 5" display ----
disp_w        = 121;      // display board width  (mm)
disp_h        = 78;       // display board height (mm)
screen_w      = 110;      // visible screen width  (opening in the front)
screen_h      = 62;       // visible screen height
disp_hole_dx  = 111;      // display mounting-hole horizontal spacing
disp_hole_dy  = 68;       // display mounting-hole vertical spacing
disp_screw_d  = 2.8;      // clearance for M2.5/M3 display screws into posts
post_h        = 8;        // how far the display sits off the front inner wall

// ---- Raspberry Pi 5 ----
pi_w          = 85;
pi_h          = 56;
pi_hole_dx    = 58;
pi_hole_dy    = 49;
pi_standoff_h = 8;
pi_screw_d    = 2.5;

// ---- ReSpeaker (rests on TOP surface) ----
mic_dia       = 70;       // ReSpeaker board diameter (round array) — measure
mic_recess_d  = 3;        // depth of the rest recess on the top surface
mic_cable_d   = 12;       // hole through the top for the mic's USB cable

// ---- Case size / build ----
wall          = 3;        // wall thickness
tol           = 0.4;      // fit tolerance
depth         = 55;       // BIG depth: room for Pi 5 + cables behind the display
side_margin   = 12;       // extra width/height around the display -> a big box
corner_r      = 6;        // rounded outside corners

// Overall size (front face sized around the display, made generously big).
inner_w = disp_w + 2*side_margin;
inner_h = disp_h + 2*side_margin;
outer_w = inner_w + 2*wall;
outer_h = inner_h + 2*wall;

// ---------------------------------------------------------------------------
//  HELPERS
// ---------------------------------------------------------------------------
module rrect(w, h, d, r) {
    linear_extrude(d)
        offset(r = r) offset(delta = -r)
            square([w, h], center = true);
}

module post(h, od, hole_d) {
    difference() {
        cylinder(h = h, d = od);
        translate([0, 0, 1.5]) cylinder(h = h, d = hole_d);
    }
}

// ---------------------------------------------------------------------------
//  MAIN CASE
//  Oriented so the FRONT face (with the screen) is at Z = 0, and the box
//  extends back to Z = depth.  The open side faces +Z (the back).
// ---------------------------------------------------------------------------
module main_case() {
    difference() {
        union() {
            // Solid outer shell, then hollowed.
            difference() {
                rrect(outer_w, outer_h, depth + wall, corner_r);
                translate([0, 0, wall])
                    rrect(inner_w, inner_h, depth + 1, corner_r);
            }

            // ---- Display screw posts on the inside of the front wall ----
            translate([0, 0, wall])
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                    post(post_h, 7, disp_screw_d);

            // ---- Pi 5 standoffs on the inside back-left area of the floor ----
            // Mounted on the front inner wall, deeper than the display posts so
            // the Pi sits behind the display.
            translate([0, -inner_h/4, wall])
            for (sx = [-1, 1], sy = [-1, 1])
                translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                    post(pi_standoff_h, 6, pi_screw_d);
        }

        // ---- Screen opening in the front wall ----
        translate([0, 0, -1])
            rrect(screen_w, screen_h, wall + 2, 3);

        // ---- ReSpeaker rest recess + cable hole on the TOP wall ----
        // Top wall is at Y = +outer_h/2; recess cut from outside inward.
        translate([0, outer_h/2 - wall + 0.01, depth/2 + wall])
            rotate([-90, 0, 0]) {
                cylinder(h = mic_recess_d + 0.02, d = mic_dia + tol);   // rest dish
                translate([0, 0, -wall]) cylinder(h = wall*2, d = mic_cable_d); // cable hole
            }

        // ---- Port cutouts on the RIGHT wall (adjust to your Pi layout) ----
        translate([outer_w/2 - wall - 1, -14, wall + 6]) cube([wall + 4, 12, 8]); // USB-C
        translate([outer_w/2 - wall - 1, 4, wall + 6])  cube([wall + 4, 28, 10]); // HDMI/USB

        // ---- USB-A slot on the LEFT wall (ReSpeaker / keyboard) ----
        translate([-outer_w/2 - 3, -18, wall + 6]) cube([wall + 4, 34, 12]);

        // ---- Cable slot on the BOTTOM wall ----
        translate([-16, -outer_h/2 - 3, wall + 6]) cube([32, wall + 4, 10]);

        // ---- Back-cover screw holes in the four corner walls ----
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*(inner_w/2 - 4), sy*(inner_h/2 - 4), depth - 6])
                cylinder(h = 12, d = 2.5);
    }
}

// ---------------------------------------------------------------------------
//  OPTIONAL BACK COVER (screws onto the open back)
// ---------------------------------------------------------------------------
module back_cover() {
    difference() {
        rrect(outer_w, outer_h, wall, corner_r);
        // Vent slots.
        for (i = [-3:3])
            translate([i*12, 0, -1])
                rrect(5, inner_h*0.6, wall + 2, 2);
        // Corner screw holes to match the case.
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx*(inner_w/2 - 4), sy*(inner_h/2 - 4), -1])
                cylinder(h = wall + 2, d = 3.2);
    }
}

// ---------------------------------------------------------------------------
//  RENDER
// ---------------------------------------------------------------------------
if (PART == "case") main_case();
else if (PART == "backcover") back_cover();
else {
    main_case();
    translate([0, outer_h + 20, 0]) back_cover();
}
