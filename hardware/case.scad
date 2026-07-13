// ============================================================================
//  AI Lecture Note-Taker — 8 x 4 x 2 in desk box, display on mounting rails
//    * Outer body: 8" long (D) x 4" wide (W) x 2" tall (H)
//    * The 5" display is WIDER than the 4" body, so it sits ON TOP overhanging
//      the sides and screws into 4 corner EARS (holes 4 7/16" x 65 mm apart).
//      No bars and no middle hole, so the HDMI/USB connectors have room.
//    * Screen stays landscape (normal orientation).
//    * ReSpeaker flat on the top at the back.
//    * Pi inside; USB/Ethernet out the FRONT, power/HDMI out the LEFT.
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
// ============================================================================

PART = "both";
$fn = 64;
in = 25.4;

// --- outer size -----------------------------------------------------------
W = 4*in;  D = 8*in;  H = 2*in;              // 101.6 x 203.2 x 50.8
wall = 3; tol = 0.4; margin = 6; edge_r = 8;
inner_h = H - 2*wall;

// --- display (landscape, overhangs the width; screws to 4 corner ears) ----
disp_x = 120.7; disp_y = 74.7;               // board size
hole_dx = 4.875*in;                          // 123.8  side-to-side screw spacing (4 7/8")
hole_dy = 3.875*in;                          // 98.4   front-back screw spacing (3 7/8")
disp_screw_d = 2.8;
ear_h = 5;                                   // small standoff under the display corners

// --- ReSpeaker ------------------------------------------------------------
mic_dia = 2.75*in; mic_recess_d = 0.0625*in; mic_cable_d = 12;  // 2 3/4" dia, 1/16" recess
mic_screw_d = 2.4;                            // pilot for the ReSpeaker screws
// ReSpeaker screw holes, relative to the speaker center (inches).
mic_screws = [ [-0.78125, 0.4375], [0.78125, 0.4375], [0.34375, -1.0625] ];

// --- Pi 4 (rotated: USB/LAN faces FRONT, power/HDMI faces LEFT) ------------
pi_w = 88.9; pi_h = 57.2; pi_hole_dx = 58; pi_hole_dy = 49;
pi_standoff_h = 4; pi_screw_d = 2.5;
span_x = pi_h; span_y = pi_w;
hole_x = 1.9375*in;   // 49.2  Pi hole spacing across the width (1 15/16")
hole_y = 2.3125*in;   // 58.7  Pi hole spacing top-to-bottom (2 5/16")

// --- placement ------------------------------------------------------------
// placed so both front/back ears stay inside the front wall
disp_cy = -D/2 + margin + hole_dy/2;         // display toward the front
mic_cy  =  D/2 - margin - mic_dia/2;          // speaker at the back
// cable slot moved back to just in front of the speaker (clear of the display)
slot_cy = mic_cy - mic_dia/2 - 8;
// Pi pushed all the way to the LEFT wall
pi_cx = -W/2 + wall + span_x/2 + 2;
pi_cy = -D/2 + wall + margin + span_y/2;

port_z = wall + pi_standoff_h + 6;
// Corner lid screws (lid bolts down to the base).
lid_screw_inset = 9;   // in from the corners
lid_screw_d = 2.6;     // pilot in the base posts (M3 self-tap)
// Extra rectangular hole on the FRONT wall (same wall as the Pi's bottom
// ports), up in the TOP-RIGHT area. 3/4" tall x 1" long.
extra_hole_h   = 0.75*in;       // 19.05 tall
extra_hole_len = 1.0*in;        // 25.4  long (across, along X)
extra_hole_x = W/2 - 16;        // toward the right
extra_hole_z = inner_h - 10;    // near the top
// Second hole on the RIGHT (+X) wall (same 3/4" x 1"): centered on the
// display front-to-back, and pushed to the very top of the wall.
extra2_y = disp_cy;                              // centered on the display
extra2_z = inner_h + wall - extra_hole_h/2 - 0.25*in;   // 1/4" down from the top
// Front (bottom) opening: one hole 2.1" wide x 3/4" tall.
front_hole_w = 2.1*in;   // 53.3
front_hole_h = 0.75*in;  // 19.05
// Left (side) opening: one slot spanning between the two Pi holes.
left_slot_h = 0.5*in;    // 12.7  slot height
left_slot_endgap = 3;    // reach right up to each mounting hole (standoff edge)

// --- helpers --------------------------------------------------------------
module boxZ(w,d,h,r){ linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w,d],center=true); }
module post(h,od,hd){ difference(){ cylinder(h=h,d=od);
    translate([0,0,1.5]) cylinder(h=h,d=hd);} }
// Front (bottom) wall: one rectangular opening, centered on the Pi.
module cut_front(){
    translate([pi_cx, -D/2 + wall/2, port_z])
        cube([front_hole_w, wall*3, front_hole_h], center=true);
}
// Left wall: one slot spanning between the two Pi mounting holes (in Y).
module cut_left(){
    len = hole_y - 2*left_slot_endgap;
    translate([-W/2 + wall/2, pi_cy, port_z])
        cube([wall*3, len, left_slot_h], center=true);
}

// --- base tray ------------------------------------------------------------
module base_tray(){
    union(){
        difference(){
            boxZ(W, D, inner_h+wall, edge_r);
            translate([0,0,wall]) boxZ(W-2*wall, D-2*wall, inner_h+1, edge_r-wall);
            cut_front(); cut_left();
            // 3/4" tall x 1" long hole on the FRONT wall, top-right.
            translate([extra_hole_x, -D/2, extra_hole_z])
                cube([extra_hole_len, wall*3, extra_hole_h], center=true);
            // Second hole on the RIGHT (+X) wall.
            translate([W/2, extra2_y, extra2_z])
                cube([wall*3, extra_hole_len, extra_hole_h], center=true);
        }
        translate([pi_cx, pi_cy, wall])
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*hole_x/2, sy*hole_y/2, 0]) post(pi_standoff_h,6,pi_screw_d);
        // Corner screw posts (back two only; front ones removed to clear the Pi).
        for(sx=[-1,1],sy=[1])
            translate([sx*(W/2-lid_screw_inset), sy*(D/2-lid_screw_inset), wall])
                post(inner_h, 8, lid_screw_d);
    }
}

// --- top lid: 4 corner mounting ears for the display (no bars, no big hole) -
module top_lid(){
    difference(){
        union(){
            boxZ(W, D, wall, edge_r);                          // plate
            translate([0,0,-6]) difference(){                  // rim into base
                boxZ(W-2*wall-tol, D-2*wall-tol, 6, edge_r-wall);
                translate([0,0,-1]) boxZ(W-2*wall-tol-4, D-2*wall-tol-4, 8, edge_r-wall); }
            // Four mounting ears at the display's screw holes (112.7 x 65 mm).
            // The side holes sit just outside the 4" body, so each ear is a
            // small bracket reaching out from the top edge to a screw boss.
            for(sx=[-1,1], sy=[-1,1]){
                ex = sx*hole_dx/2;  ey = disp_cy + sy*hole_dy/2;
                hull(){
                    translate([sx*(W/2-8), ey, wall/2]) cube([2,16,wall], center=true);
                    translate([ex, ey, wall/2]) cube([12,16,wall], center=true);
                }
                translate([ex, ey, wall]) post(ear_h, 9, disp_screw_d);
            }
            // ReSpeaker mounting bosses (3 holes) hanging below the lid.
            // Hole pattern rotated 180 deg about the speaker center.
            for(s = mic_screws)
                translate([-s[0]*in, mic_cy - s[1]*in, -6]) cylinder(h=6+wall, d=6);
        }
        // Speaker dish (flat) + cable hole + grille at the back.
        translate([0, mic_cy, wall-mic_recess_d]) cylinder(h=mic_recess_d+1, d=mic_dia+tol);
        translate([0, mic_cy, -1]) cylinder(h=wall+2, d=mic_cable_d);
        // ReSpeaker screw pilot holes at the 3 coordinates (rotated 180 deg).
        for(s = mic_screws)
            translate([-s[0]*in, mic_cy - s[1]*in, -8]) cylinder(h=wall+10, d=mic_screw_d);
        // Cable slot between display and speaker.
        translate([0, slot_cy, -1]) boxZ(30, 9, wall+2, 4);
        // Corner clearance holes (back two only) matching the base posts.
        for(sx=[-1,1],sy=[1])
            translate([sx*(W/2-lid_screw_inset), sy*(D/2-lid_screw_inset), -1])
                cylinder(h=wall+2, d=3.4);
    }
}

// Shown in black (the real color comes from printing in BLACK filament).
color("black")
if(PART=="base") base_tray();
else if(PART=="lid") top_lid();
else { base_tray(); translate([W+30,0,0]) top_lid(); }
