// ============================================================================
//  AI Lecture Note-Taker — HANDHELD console
//    * Sized to hold like a big phone, with rounded grip edges
//    * TOP LID: 5" screen + ReSpeaker on top, both facing up
//    * A cable slot BETWEEN the screen and the speaker for the mic's wire
//    * BASE TRAY: Pi inside with cable room
//    * Wall cutouts placed at the Pi's ACTUAL ports (Pi 4 or Pi 5 preset)
//
//  EXPORT:  set PART="base" -> F6 -> Export STL;  then PART="lid" -> export.
//  PRINT:   PLA/PETG, 0.2 mm, 3 walls, 15-20% infill.
// ============================================================================

PART = "both";            // "base", "lid", or "both"
PI_MODEL = "pi4";         // matches the Pi 4 in the photo
$fn = 64;

// ---------------------------------------------------------------------------
//  USER DIMENSIONS — measure your hardware and edit these
// ---------------------------------------------------------------------------

// ---- 5" display (in the LID, facing up) ----  measured 4.75 x 2.94 in
disp_w        = 120.7;    // 4.75 in
disp_h        = 74.7;     // 2.94 in
disp_thick    = 5;
screen_w      = 109;      // visible screen (tweak to your bezel)
screen_h      = 61;
disp_hole_dx  = 111;      // display screw-hole spacing X (0 = no posts) — VERIFY
disp_hole_dy  = 65;
disp_screw_d  = 2.8;

// ---- ReSpeaker (in the LID, facing up) ----
mic_dia       = 70;       // measured 7 cm diameter
mic_recess_d  = 3;
mic_cable_d   = 12;       // hole directly under the mic

// ---- Raspberry Pi (on the BASE floor) ----  measured 3.5 x 2.25 in
pi_w          = 88.9;     // 3.5 in  (long side, X)
pi_h          = 57.2;     // 2.25 in (short side, Y)
pi_hole_dx    = 58;       // standard Pi mounting-hole spacing
pi_hole_dy    = 49;
pi_standoff_h = 3;        // low, to keep it thin/handheld
pi_screw_d    = 2.5;

// ---- REAL depth of parts (this is what sets how thick the case must be) ----
// The display's HDMI/USB connectors stick out the BACK of the board; measure
// how far they + a plugged-in cable's bend need.  This is the #1 dimension
// people get wrong.
disp_back_clear = 16;     // clearance needed behind the display for connectors
pi_tall         = 18;     // tallest part of the Pi (USB/Ethernet stack)

// ---- Build ----
wall          = 2.6;
tol           = 0.4;
margin        = 7;        // margin around the display
gap           = 12;       // gap between screen and speaker (cable slot lives here)
grip_r        = 12;       // rounded corners for grip

// Internal height must clear whichever is taller: the Pi, or the display's
// rear connectors.  They sit in different areas (Pi under the mic, connectors
// under the display) so we don't add them — but the cavity must fit the max.
inner_h = max(pi_tall, disp_back_clear) + pi_standoff_h + 3;   // ~= 27 mm

// ---- Footprint (as small as a 5" screen + 70 mm mic allow) ----
top_w   = max(disp_w, mic_dia) + 2*margin;              // ~135 mm wide
top_d   = disp_h + gap + mic_dia + 2*margin;            // ~174 mm tall
outer_w = top_w;
outer_d = top_d;
inner_w = outer_w - 2*wall;
inner_d = outer_d - 2*wall;

// On-top layout: screen toward the FRONT (-Y), speaker toward the BACK (+Y).
disp_cy = -outer_d/2 + margin + disp_h/2;
mic_cy  =  outer_d/2 - margin - mic_dia/2;
slot_cy = (disp_cy + disp_h/2 + mic_cy - mic_dia/2) / 2;

// The Pi sits UNDER the mic (back half) so it clears the display's rear
// connectors (which hang down under the display in the front half).
pi_cx = 0;
pi_cy = mic_cy;

// ---------------------------------------------------------------------------
//  PORTS — two big openings so EVERY Pi port is reachable (no fiddly per-port
//  alignment). Orient the Pi so its two port edges face the back (+Y) and
//  right (+X) walls; the wide slots expose the whole port row.
// ---------------------------------------------------------------------------
port_z    = wall + pi_standoff_h + 5;   // vertical center of the openings
back_slot_w  = pi_w * 0.85;             // spans the power/HDMI/audio row
back_slot_h  = 15;
right_slot_w = pi_h * 0.80;             // spans the USB/Ethernet row
right_slot_h = 20;

// ---------------------------------------------------------------------------
//  HELPERS
// ---------------------------------------------------------------------------
module rrect(w, h, d, r) {
    linear_extrude(d) offset(r = r) offset(delta = -r)
        square([w, h], center = true);
}
module post(h, od, hole_d) {
    difference() { cylinder(h = h, d = od);
        translate([0, 0, 1.5]) cylinder(h = h, d = hole_d); }
}

// ---------------------------------------------------------------------------
//  BASE TRAY
// ---------------------------------------------------------------------------
module base_tray() {
    difference() {
        union() {
            difference() {
                rrect(outer_w, outer_d, inner_h + wall, grip_r);
                translate([0, 0, wall]) rrect(inner_w, inner_d, inner_h + 1, grip_r - wall);
            }
            // Pi standoffs (under the mic / back half, clear of the display's
            // rear connectors).
            translate([pi_cx, pi_cy, wall])
                for (sx = [-1, 1], sy = [-1, 1])
                    translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                        post(pi_standoff_h, 6, pi_screw_d);
            // Seat lip for the lid.
            difference() {
                rrect(inner_w, inner_d, inner_h + wall, grip_r - wall);
                translate([0,0,-1]) rrect(inner_w - 6, inner_d - 6, inner_h + wall + 2, grip_r - wall);
                translate([0,0,-1]) rrect(inner_w, inner_d, inner_h - 2, grip_r - wall);
            }
        }
        // Big port opening on the BACK (+Y) wall — power / HDMI / audio row.
        translate([pi_cx, outer_d/2 - wall/2, port_z])
            cube([back_slot_w, wall*2 + 2, back_slot_h], center = true);
        // Big port opening on the RIGHT (+X) wall — USB / Ethernet row.
        translate([outer_w/2 - wall/2, pi_cy, port_z])
            cube([wall*2 + 2, right_slot_w, right_slot_h], center = true);
    }
}

// ---------------------------------------------------------------------------
//  TOP LID  (screen + speaker facing up, cable slot between them)
// ---------------------------------------------------------------------------
module top_lid() {
    difference() {
        union() {
            rrect(outer_w, outer_d, wall, grip_r);
            // Locating rim into the base.
            translate([0, 0, -6])
                difference() {
                    rrect(inner_w - tol, inner_d - tol, 6, grip_r - wall);
                    translate([0,0,-1]) rrect(inner_w - 6 - tol, inner_d - 6 - tol, 8, grip_r - wall);
                }
            // Display screw posts under the lid.
            if (disp_hole_dx > 0)
                translate([0, disp_cy, -disp_thick - 2])
                    for (sx = [-1, 1], sy = [-1, 1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                            post(disp_thick + 2, 7, disp_screw_d);
        }
        // Screen opening + pocket.
        translate([0, disp_cy, -1]) rrect(screen_w, screen_h, wall + 2, 3);
        translate([0, disp_cy, wall - disp_thick]) rrect(disp_w + 2*tol, disp_h + 2*tol, disp_thick + 1, 2);

        // ReSpeaker dish + its own cable hole + grille.
        translate([0, mic_cy, wall - mic_recess_d]) cylinder(h = mic_recess_d + 1, d = mic_dia + tol);
        translate([0, mic_cy, -1]) cylinder(h = wall + 2, d = mic_cable_d);
        for (ring = [1:4])
            for (a = [0 : 360/(ring*6) : 359])
                rotate([0, 0, a])
                    translate([0, mic_cy, -1])
                        translate([ring*(mic_dia/2/5), 0, 0]) cylinder(h = wall + 2, d = 3);

        // >>> Cable slot BETWEEN the screen and the speaker, for the mic's USB
        // wire coming up from the Pi. <<<
        translate([0, slot_cy, -1]) rrect(34, 9, wall + 2, 4);
    }
}

// ---------------------------------------------------------------------------
if (PART == "base") base_tray();
else if (PART == "lid") top_lid();
else { base_tray(); translate([outer_w + 20, 0, 0]) top_lid(); }
