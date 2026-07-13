// ============================================================================
//  AI Lecture Note-Taker — DESKTOP CONSOLE (matches the cardboard prototype)
//    * Box that sits on a desk
//    * DISPLAY on the upright FRONT face (landscape), screwed to posts
//    * ReSpeaker rests flat in a dish on the TOP, toward the back
//    * Raspberry Pi inside on the floor
//    * OPEN BACK so every Pi port is reachable and cables route out
//
//  EXPORT:  PART="body" -> F6 -> File > Export > Export as STL
//  PRINT:   front face DOWN on the bed (screen opening on the plate) so the
//           display posts and top overhang print cleanly. PLA/PETG, 0.2 mm.
// ============================================================================

PART = "body";           // "body" (there's only one part; back is open)
$fn = 64;

// --- measured parts -------------------------------------------------------
disp_w = 120.7; disp_h = 74.7;          // 4.75 x 2.94 in display board
screen_w = 109; screen_h = 61;          // visible screen (tweak to your bezel)
disp_hole_dx = 111; disp_hole_dy = 65;  // display corner-hole spacing (VERIFY)
disp_screw_d = 2.8;

mic_dia = 70;                            // ReSpeaker (7 cm)
mic_recess_d = 3; mic_cable_d = 12;

pi_w = 88.9; pi_h = 57.2;                // 3.5 x 2.25 in Pi 4
pi_hole_dx = 58; pi_hole_dy = 49;
pi_standoff_h = 4; pi_screw_d = 2.5;

// --- box build ------------------------------------------------------------
wall   = 3;
tol    = 0.4;
margin = 8;
edge_r = 6;                              // rounded vertical edges

W = disp_w + 2*margin;                   // width  (~137)  fits display on front
H = disp_h + 2*margin;                   // height (~91)   front face = display
D = mic_dia + 2*margin + 20;             // depth  (~106)  speaker on top + Pi room

// Display centered on the FRONT (-Y) wall.
disp_cx = 0;
disp_cz = H/2;
// ReSpeaker centered on the TOP, toward the BACK (+Y).
mic_cy  = D/2 - margin - mic_dia/2;
// Pi on the floor, pushed toward the back so its ports reach the open back.
pi_cx = 0;
pi_cy = D/2 - pi_h/2 - wall - 4;

// --- helpers --------------------------------------------------------------
module rrect(w, d, r) {
    linear_extrude(1) offset(r=r) offset(delta=-r) square([w, d], center=true);
}
module boxZ(w, d, h, r) { linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w, d], center=true); }
module post(h, od, hd) {
    difference() { cylinder(h=h, d=od); translate([0,0,1.5]) cylinder(h=h, d=hd); }
}

// --- body -----------------------------------------------------------------
module body() {
    difference() {
        boxZ(W, D, H, edge_r);                              // solid box

        // Hollow interior (keeps floor + top + front + sides; back opened below)
        translate([0,0,wall]) boxZ(W-2*wall, D-2*wall, H-2*wall, edge_r-wall);

        // OPEN BACK: cut a big window through the +Y wall (leave corner pillars)
        translate([0, D/2 - wall/2, H/2 + wall/2])
            cube([W-2*wall-16, wall*3, H-2*wall], center=true);

        // SCREEN opening through the FRONT (-Y) wall.
        translate([disp_cx, -D/2, disp_cz])
            rotate([90,0,0]) rrect_extrude(screen_w, screen_h, wall*3, 3);

        // SPEAKER dish + cable hole + grille in the TOP wall (z = H).
        translate([0, mic_cy, H - mic_recess_d])
            cylinder(h = mic_recess_d + 1, d = mic_dia + tol);
        translate([0, mic_cy, H - wall - 1])
            cylinder(h = wall + 2, d = mic_cable_d);
        for (ring=[1:4]) for (a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0, mic_cy, H-wall-1])
                translate([ring*(mic_dia/2/5), 0, 0]) cylinder(h=wall+2, d=3);

        // Cable slot on top between the display top and the speaker.
        translate([0, mic_cy - mic_dia/2 - 8, H - wall - 1])
            rrect_extrude(30, 9, wall+2, 4);
    }

    // Display screw posts on the INSIDE of the front wall.
    translate([disp_cx, -D/2 + wall, disp_cz])
        for (sx=[-1,1], sz=[-1,1])
            translate([sx*disp_hole_dx/2, 0, sz*disp_hole_dy/2])
                rotate([-90,0,0]) post(7, 7, disp_screw_d);

    // Pi standoffs on the floor.
    translate([pi_cx, pi_cy, wall])
        for (sx=[-1,1], sy=[-1,1])
            translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                post(pi_standoff_h, 6, pi_screw_d);
}

// helper: an extruded rounded rectangle hole of size w x h, depth d
module rrect_extrude(w, h, d, r) {
    linear_extrude(d) offset(r=r) offset(delta=-r) square([w, h], center=true);
}

// --- render ---------------------------------------------------------------
body();
