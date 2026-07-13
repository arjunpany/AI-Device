// ============================================================================
//  AI Lecture Note-Taker — WAISTED handheld enclosure
//    * WIDE only at the display end (to fit the 5" screen)
//    * NARROW grip for the rest so you can actually hold it
//    * Screen + ReSpeaker on top, both facing up; Pi inside the wide head
//    * Display screw posts are ATTACHED to the lid
//    * Per-port Pi 4 cutouts (flip toggles if a row is mirrored)
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
//  PRINT:   PLA/PETG, 0.2 mm, 3 walls, 15-20% infill
// ============================================================================

PART = "both";            // "base", "lid", or "both"
$fn = 64;

// --- measured parts -------------------------------------------------------
disp_w        = 120.7;    // display board  (4.75 in)
disp_h        = 74.7;     //                (2.94 in)
disp_thick    = 5;
screen_w      = 109;      // visible screen opening
screen_h      = 61;
disp_hole_dx  = 111;      // display screw-hole spacing (VERIFY on your board)
disp_hole_dy  = 65;
disp_screw_d  = 2.8;

mic_dia       = 70;       // ReSpeaker (7 cm)
mic_recess_d  = 3;
mic_cable_d   = 12;

pi_w          = 88.9;     // Pi 4  (3.5 in, long side X)
pi_h          = 57.2;     //       (2.25 in, short side Y)
pi_hole_dx    = 58;
pi_hole_dy    = 49;
pi_standoff_h = 3;
pi_screw_d    = 2.5;

// --- build ----------------------------------------------------------------
wall          = 2.6;
tol           = 0.4;
margin        = 7;
grip_extra    = 10;       // extra length on the grip for your hand
grip_r        = 14;       // big fillets, comfy to hold

disp_back_clear = 16;     // depth needed behind the display for its connectors
pi_tall         = 18;
inner_h = max(pi_tall, disp_back_clear) + pi_standoff_h + 3;   // ~24 mm

// --- footprint: a WIDE head + a NARROW grip -------------------------------
head_w = disp_w  + 2*margin;      // ~135 mm  (wide, holds the screen)
head_d = disp_h  + 2*margin;      // ~89 mm
grip_w = mic_dia + 2*margin;      // ~84 mm  (narrow, you hold this)
grip_d = mic_dia + 2*margin + grip_extra;

outer_w = head_w;                 // overall max width
outer_d = head_d + grip_d;

head_cy = -outer_d/2 + head_d/2;  // wide head toward the FRONT (-Y)
grip_cy =  outer_d/2 - grip_d/2;  // narrow grip toward the BACK  (+Y)

disp_cy = head_cy;                // screen in the head
mic_cy  = grip_cy;                // speaker on the grip
pi_cx   = 0;                      // Pi inside the head
pi_cy   = head_cy;
slot_cy = -outer_d/2 + head_d;    // cable slot at the head/grip waist

// --- Pi 4 ports -----------------------------------------------------------
// Pi lies chips-UP with its HDMI/power edge toward the FRONT (-Y) wall; that
// puts the USB/Ethernet edge on the RIGHT (+X) wall.  Flip a row if mirrored.
flip_front = false;
flip_right = false;
port_z = wall + pi_standoff_h + 5;
front_ports = [ [ 7.7,12,8],[26.0,9,8],[39.5,9,8],[54.0,9,9] ]; // USBC,HDMI,HDMI,AV
right_ports = [ [10.5,17,15],[29.0,16,18],[47.0,16,18] ];        // LAN,USB,USB

// --- helpers --------------------------------------------------------------
module outline2d(inset) {
    offset(delta = -inset)
        offset(r = grip_r) offset(delta = -grip_r)
            union() {
                translate([0, head_cy]) square([head_w, head_d], center = true);
                translate([0, grip_cy]) square([grip_w, grip_d], center = true);
            }
}
module post(h, od, hole_d) {
    difference() { cylinder(h = h, d = od);
        translate([0,0,1.5]) cylinder(h = h, d = hole_d); }
}
module cut_front_ports() {
    for (p = front_ports) {
        x = flip_front ? pi_cx + pi_w/2 - p[0] : pi_cx - pi_w/2 + p[0];
        translate([x, -outer_d/2 + wall/2, port_z])
            cube([p[1], wall*2 + 2, p[2]], center = true);
    }
}
module cut_right_ports() {
    for (p = right_ports) {
        y = flip_right ? pi_cy + pi_h/2 - p[0] : pi_cy - pi_h/2 + p[0];
        translate([outer_w/2 - wall/2, y, port_z])
            cube([wall*2 + 2, p[1], p[2]], center = true);
    }
}

// --- base tray ------------------------------------------------------------
module base_tray() {
    union() {
        difference() {
            linear_extrude(inner_h + wall) outline2d(0);
            translate([0,0,wall]) linear_extrude(inner_h + 1) outline2d(wall);
            cut_front_ports();
            cut_right_ports();
        }
        // Pi cradle: standoffs + corner guides (in the head).
        translate([pi_cx, pi_cy, wall]) {
            for (sx=[-1,1], sy=[-1,1])
                translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                    post(pi_standoff_h, 6, pi_screw_d);
            for (sx=[-1,1], sy=[-1,1])
                translate([sx*(pi_w/2 + tol), sy*(pi_h/2 + tol), 0])
                    for (d = [[-sx*3,0,1.6,8],[0,-sy*3,8,1.6]])
                        translate([d[0],d[1],0])
                            cube([d[2],d[3],pi_standoff_h+5], center=true);
        }
    }
}

// --- top lid --------------------------------------------------------------
module top_lid() {
    difference() {
        union() {
            linear_extrude(wall) outline2d(0);                 // top plate
            translate([0,0,-6])                                // locating rim
                linear_extrude(6)
                    difference() { outline2d(wall + tol);
                                   offset(delta=-2.4) outline2d(wall + tol); }
            // Display screw posts — attached to the plate underside.
            if (disp_hole_dx > 0)
                translate([0, disp_cy, -(disp_thick + 2)])
                    for (sx=[-1,1], sy=[-1,1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                            post(disp_thick + 2, 7, disp_screw_d);
        }
        // Screen opening (board rests against the plate border from below).
        translate([0, disp_cy, -1]) rrect_hole(screen_w, screen_h, wall + 2, 3);
        // ReSpeaker dish + cable hole + grille.
        translate([0, mic_cy, wall - mic_recess_d]) cylinder(h=mic_recess_d+1, d=mic_dia+tol);
        translate([0, mic_cy, -1]) cylinder(h=wall+2, d=mic_cable_d);
        for (ring=[1:4]) for (a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0,mic_cy,-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=wall+2, d=3);
        // Cable slot at the waist, for the mic wire.
        translate([0, slot_cy, -1]) rrect_hole(30, 9, wall+2, 4);
    }
}
module rrect_hole(w,h,d,r){ linear_extrude(d) offset(r=r) offset(delta=-r) square([w,h],center=true); }

// --- render ---------------------------------------------------------------
if (PART == "base") base_tray();
else if (PART == "lid") top_lid();
else { base_tray(); translate([outer_w + 20, 0, 0]) top_lid(); }
