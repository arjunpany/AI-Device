// ============================================================================
//  AI Lecture Note-Taker — CONSOLE enclosure
//    * Flat box that sits on a desk
//    * TOP LID holds the 5" screen AND the ReSpeaker, both facing up
//    * BASE TRAY holds the Pi with plenty of room for cables
//    * Port cutouts in the walls so you can plug into ALL the Pi's ports
//    * Cable pass-through holes + open-underside routing
//    * Lid lifts off for wiring
//
//  HOW TO USE
//    1. Install OpenSCAD (free): https://openscad.org
//    2. Open this file.  MEASURE your boards and edit USER DIMENSIONS.
//    3. Export each part:  set PART="base" -> F6 -> Export STL;
//                          set PART="lid"  -> F6 -> Export STL.
//    4. Print.  PLA/PETG, 0.2 mm, 3 walls, 15-20% infill.
// ============================================================================

PART = "both";            // "base", "lid", or "both" (preview side by side)
$fn = 64;

// ---------------------------------------------------------------------------
//  USER DIMENSIONS — measure your hardware and edit these
// ---------------------------------------------------------------------------

// ---- 5" display (mounted in the LID, screen facing up) ----
disp_w        = 121;      // display board width  (mm)
disp_h        = 78;       // display board height (mm)
disp_thick    = 5;        // board thickness incl. rear components
screen_w      = 110;      // visible screen width  (the opening in the lid)
screen_h      = 62;       // visible screen height
disp_hole_dx  = 111;      // display mounting-hole spacing, X  (0 = no posts)
disp_hole_dy  = 68;       // display mounting-hole spacing, Y
disp_screw_d  = 2.8;      // clearance for the display screws

// ---- ReSpeaker (also in the LID, resting in a dish) ----
mic_dia       = 70;       // ReSpeaker board diameter (mm)
mic_recess_d  = 3;        // depth of the rest dish
mic_cable_d   = 12;       // cable pass-through under the mic

// ---- Raspberry Pi (sits on the BASE floor) ----
pi_w          = 85;
pi_h          = 56;
pi_hole_dx    = 58;
pi_hole_dy    = 49;
pi_standoff_h = 6;
pi_screw_d    = 2.5;

// ---- Case build ----
wall          = 3;        // wall thickness
tol           = 0.4;      // fit tolerance
margin        = 14;       // space around the display on the top
gap           = 12;       // gap between display and mic on top
inner_h       = 45;       // internal height: room for Pi + cables
lid_h         = wall;     // lid plate thickness (recess adds more)

// ---- Footprint (derived so the screen + mic both fit on top) ----
top_w   = max(disp_w, mic_dia) + 2*margin;
top_d   = disp_h + gap + mic_dia + 2*margin;
outer_w = top_w;
outer_d = top_d;
inner_w = outer_w - 2*wall;
inner_d = outer_d - 2*wall;

// On-top layout: display toward the FRONT (-Y), mic toward the BACK (+Y).
disp_cy = -outer_d/2 + margin + disp_h/2;
mic_cy  =  outer_d/2 - margin - mic_dia/2;

// ---- PORT CUTOUTS (edit to match your Pi's port layout) ----
// Big, generous openings so every cable fits.  Positions are the center of
// each opening on its wall, measured from the case center.
right_port_w  = 62;  right_port_h = 16;  right_port_cy = 0;   // +X wall (USB/LAN)
back_port_w   = 46;  back_port_h  = 14;  back_port_cx = 0;    // +Y wall (power/HDMI)
port_z        = wall + pi_standoff_h + 3;  // height of port centers off the floor

// ---------------------------------------------------------------------------
//  HELPERS
// ---------------------------------------------------------------------------
module rrect(w, h, d, r) {
    linear_extrude(d) offset(r = r) offset(delta = -r)
        square([w, h], center = true);
}
module post(h, od, hole_d) {
    difference() {
        cylinder(h = h, d = od);
        translate([0, 0, 1.5]) cylinder(h = h, d = hole_d);
    }
}

// ---------------------------------------------------------------------------
//  BASE TRAY — floor + walls + Pi standoffs + port cutouts
// ---------------------------------------------------------------------------
module base_tray() {
    difference() {
        union() {
            // Outer shell with a floor, open top.
            difference() {
                rrect(outer_w, outer_d, inner_h + wall, 6);
                translate([0, 0, wall])
                    rrect(inner_w, inner_d, inner_h + 1, 4);
            }
            // Pi standoffs on the floor (shifted toward the front-left so the
            // back-right stays clear for cable routing).
            translate([-inner_w/2 + pi_w/2 + 6, -inner_d/2 + pi_h/2 + 6, wall])
                for (sx = [-1, 1], sy = [-1, 1])
                    translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                        post(pi_standoff_h, 6, pi_screw_d);
            // Lip around the top rim for the lid to seat on.
            difference() {
                rrect(inner_w, inner_d, inner_h + wall, 4);
                translate([0, 0, -1]) rrect(inner_w - 2*3, inner_d - 2*3, inner_h + wall + 2, 3);
                translate([0, 0, -1]) rrect(inner_w, inner_d, inner_h - 2, 4);
            }
        }

        // ---- Right wall port opening (USB / Ethernet cluster) ----
        translate([outer_w/2 - wall - 1, right_port_cy, port_z])
            cube([wall + 4, right_port_w, right_port_h], center = true);

        // ---- Back wall port opening (power / HDMI) ----
        translate([back_port_cx, outer_d/2 - wall - 1, port_z])
            rotate([0, 0, 90])
                cube([wall + 4, back_port_w, back_port_h], center = true);

        // ---- Left wall cable/grommet holes ----
        for (i = [-1, 0, 1])
            translate([-outer_w/2 - 1, i*20, port_z])
                rotate([0, 90, 0]) cylinder(h = wall + 4, d = 12);

        // ---- Floor vents ----
        for (i = [-2:2])
            translate([i*14, -inner_d/4, -0.5])
                rrect(5, inner_d*0.4, wall + 1, 2);
    }
}

// ---------------------------------------------------------------------------
//  TOP LID — screen opening + display pocket, mic dish, both facing up
// ---------------------------------------------------------------------------
module top_lid() {
    difference() {
        union() {
            // Lid plate.
            rrect(outer_w, outer_d, wall, 6);
            // Drop-in rim that locates the lid into the base opening.
            translate([0, 0, -6])
                difference() {
                    rrect(inner_w - tol, inner_d - tol, 6, 4);
                    translate([0, 0, -1]) rrect(inner_w - 2*3 - tol, inner_d - 2*3 - tol, 8, 3);
                }
            // Display screw posts hanging under the lid.
            if (disp_hole_dx > 0)
                translate([0, disp_cy, -disp_thick - 2])
                    for (sx = [-1, 1], sy = [-1, 1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                            post(disp_thick + 2, 7, disp_screw_d);
        }

        // ---- Screen opening (screen shows through, facing up) ----
        translate([0, disp_cy, -1])
            rrect(screen_w, screen_h, wall + 2, 3);
        // Pocket underneath so the display board rests flush.
        translate([0, disp_cy, wall - disp_thick])
            rrect(disp_w + 2*tol, disp_h + 2*tol, disp_thick + 1, 2);

        // ---- ReSpeaker dish + grille + cable hole (facing up) ----
        translate([0, mic_cy, wall - mic_recess_d])
            cylinder(h = mic_recess_d + 1, d = mic_dia + tol);      // rest dish
        translate([0, mic_cy, -1]) cylinder(h = wall + 2, d = mic_cable_d); // cable hole
        // sound holes ring
        for (ring = [1:4])
            for (a = [0 : 360/(ring*6) : 359])
                rotate([0, 0, a])
                    translate([0, mic_cy, -1])
                        translate([ring*(mic_dia/2/5), 0, 0])
                            cylinder(h = wall + 2, d = 3);
    }
}

// ---------------------------------------------------------------------------
//  RENDER
// ---------------------------------------------------------------------------
if (PART == "base") base_tray();
else if (PART == "lid") top_lid();
else {
    base_tray();
    translate([outer_w + 20, 0, 0]) top_lid();
}
