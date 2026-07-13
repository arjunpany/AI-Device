// ============================================================================
//  AI Lecture Note-Taker — matches the cardboard prototype
//    * Box on the desk; you look DOWN at it
//    * DISPLAY flat on the top, front half, facing up (screwed to posts)
//    * ReSpeaker flat on a RAISED step at the back, facing up
//    * Raspberry Pi inside on the floor, under the speaker
//    * Big opening in the back wall for the Pi ports + cables
//    * Two parts: BASE tray + TOP lid (lid lifts off to wire it)
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
//  PRINT:   base open-side up.  lid: plate-down, posts up (light support
//           under the raised speaker step).  PLA/PETG, 0.2 mm.
// ============================================================================

PART = "both";           // "base", "lid", or "both"
$fn = 64;

// --- measured parts -------------------------------------------------------
disp_w = 120.7; disp_h = 74.7; disp_thick = 5;   // 4.75 x 2.94 in
screen_w = 109; screen_h = 61;                   // visible screen opening
disp_hole_dx = 111; disp_hole_dy = 65;           // display corner holes (VERIFY)
disp_screw_d = 2.8;

mic_dia = 70; mic_recess_d = 3; mic_cable_d = 12; // ReSpeaker 7 cm

pi_w = 88.9; pi_h = 57.2;                         // 3.5 x 2.25 in Pi 4
pi_hole_dx = 58; pi_hole_dy = 49; pi_standoff_h = 4; pi_screw_d = 2.5;

// --- build ----------------------------------------------------------------
wall = 3; tol = 0.4; margin = 8; gap = 12;
edge_r = 8;
step_h = 14;                                      // how high the speaker sits
disp_back_clear = 16; pi_tall = 18;
inner_h = max(pi_tall, disp_back_clear) + pi_standoff_h + 3;   // ~25

W = disp_w + 2*margin;                            // ~137 wide
D = disp_h + gap + mic_dia + 2*margin;            // ~171 deep

disp_cy = -D/2 + margin + disp_h/2;               // display on the front half
mic_cy  =  D/2 - margin - mic_dia/2;              // speaker on the back
pi_cx = 0; pi_cy = mic_cy;                        // Pi under the speaker
slot_cy = disp_cy + disp_h/2 + 8;                 // cable slot behind the screen
port_h = 20;

// --- helpers --------------------------------------------------------------
module boxZ(w,d,h,r){ linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w,d],center=true); }
module rr(w,d,h,r){ linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w,d],center=true); }
module post(h,od,hd){ difference(){ cylinder(h=h,d=od);
    translate([0,0,1.5]) cylinder(h=h,d=hd);} }

// --- BASE tray ------------------------------------------------------------
module base_tray(){
    union(){
        difference(){
            boxZ(W, D, inner_h+wall, edge_r);
            translate([0,0,wall]) boxZ(W-2*wall, D-2*wall, inner_h+1, edge_r-wall);
            // Big back-wall opening for all Pi ports + cables.
            translate([0, D/2 - wall/2, wall + port_h/2 + 2])
                cube([W*0.6, wall*3, port_h], center=true);
        }
        // Pi standoffs (under the speaker / back).
        translate([pi_cx, pi_cy, wall])
            for (sx=[-1,1], sy=[-1,1])
                translate([sx*pi_hole_dx/2, sy*pi_hole_dy/2, 0])
                    post(pi_standoff_h, 6, pi_screw_d);
    }
}

// --- TOP lid --------------------------------------------------------------
module top_lid(){
    difference(){
        union(){
            rr(W, D, wall, edge_r);                          // top plate
            // locating rim into the base
            translate([0,0,-6])
                difference(){ rr(W-2*wall-tol, D-2*wall-tol, 6, edge_r-wall);
                    translate([0,0,-1]) rr(W-2*wall-tol-4, D-2*wall-tol-4, 8, edge_r-wall); }
            // raised speaker step at the back
            translate([0, mic_cy, wall])
                cylinder(h = step_h, d = mic_dia + 2*margin);
            // display screw posts under the front (attached to plate)
            if (disp_hole_dx > 0)
                translate([0, disp_cy, -(disp_thick+2)])
                    for (sx=[-1,1], sy=[-1,1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                            post(disp_thick+2, 7, disp_screw_d);
        }
        // Screen opening (front, facing up).
        translate([0, disp_cy, -1]) rr(screen_w, screen_h, wall+2, 3);
        // Speaker dish on top of the raised step + cable hole down through it.
        translate([0, mic_cy, wall + step_h - mic_recess_d])
            cylinder(h = mic_recess_d + 1, d = mic_dia + tol);
        translate([0, mic_cy, -1]) cylinder(h = wall + step_h + 2, d = mic_cable_d);
        for (ring=[1:4]) for (a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0, mic_cy, wall+step_h-mic_recess_d-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=mic_recess_d+3, d=3);
        // Cable slot between the screen and the speaker.
        translate([0, slot_cy, -1]) rr(30, 9, wall+2, 4);
    }
}

// --- render ---------------------------------------------------------------
if (PART=="base") base_tray();
else if (PART=="lid") top_lid();
else { base_tray(); translate([W+20,0,0]) top_lid(); }
