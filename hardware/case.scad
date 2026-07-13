// ============================================================================
//  AI Lecture Note-Taker — 8 x 4 x 2 in desk box, display on mounting rails
//    * Outer body: 8" long (D) x 4" wide (W) x 2" tall (H)
//    * The 5" display is WIDER than the 4" body, so it sits ON TOP on two
//      RAILS spaced 3.75" apart, overhanging the sides, screwed down.
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

// --- display (landscape, overhangs the width; sits on rails) --------------
disp_x = 120.7; disp_y = 74.7;               // board size
rail_gap   = 3.75*in;                        // 95.25  spacing between the rails
rail_hole_y = 65;                            // front-back screw-hole spacing (VERIFY)
disp_screw_d = 2.8;
rail_w = 12; rail_h = 6; rail_len = rail_hole_y + 18;

// --- ReSpeaker ------------------------------------------------------------
mic_dia = 70; mic_recess_d = 3; mic_cable_d = 12;

// --- Pi 4 (rotated: USB/LAN faces FRONT, power/HDMI faces LEFT) ------------
pi_w = 88.9; pi_h = 57.2; pi_hole_dx = 58; pi_hole_dy = 49;
pi_standoff_h = 4; pi_screw_d = 2.5;
span_x = pi_h; span_y = pi_w; hole_x = pi_hole_dy; hole_y = pi_hole_dx;

// --- placement ------------------------------------------------------------
disp_cy = -D/2 + margin + disp_y/2;          // display toward the front
mic_cy  =  D/2 - margin - mic_dia/2;          // speaker at the back
slot_cy = disp_cy + disp_y/2 + 8;
pi_cx = 0; pi_cy = -D/2 + wall + margin + span_y/2;

flip_front = false; flip_left = false;
port_z = wall + pi_standoff_h + 6;
front_ports = [ [10.5,17,15],[29.0,16,18],[47.0,16,18] ];        // LAN,USB,USB
left_ports  = [ [ 7.7,12,8],[26.0,9,8],[39.5,9,8],[54.0,9,9] ];  // USBC,HDMI,HDMI,AV

// --- helpers --------------------------------------------------------------
module boxZ(w,d,h,r){ linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w,d],center=true); }
module post(h,od,hd){ difference(){ cylinder(h=h,d=od);
    translate([0,0,1.5]) cylinder(h=h,d=hd);} }
module cut_front(){ for(p=front_ports){
    x = flip_front ? pi_cx+span_x/2-p[0] : pi_cx-span_x/2+p[0];
    translate([x, -D/2 + wall/2, port_z]) cube([p[1], wall*3, p[2]], center=true); } }
module cut_left(){ for(p=left_ports){
    y = flip_left ? pi_cy+span_y/2-p[0] : pi_cy-span_y/2+p[0];
    translate([-W/2 + wall/2, y, port_z]) cube([wall*3, p[1], p[2]], center=true); } }

// --- base tray ------------------------------------------------------------
module base_tray(){
    union(){
        difference(){
            boxZ(W, D, inner_h+wall, edge_r);
            translate([0,0,wall]) boxZ(W-2*wall, D-2*wall, inner_h+1, edge_r-wall);
            cut_front(); cut_left();
        }
        translate([pi_cx, pi_cy, wall])
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*hole_x/2, sy*hole_y/2, 0]) post(pi_standoff_h,6,pi_screw_d);
    }
}

// --- top lid with the two display rails -----------------------------------
module top_lid(){
    difference(){
        union(){
            boxZ(W, D, wall, edge_r);                          // plate
            translate([0,0,-6]) difference(){                  // rim into base
                boxZ(W-2*wall-tol, D-2*wall-tol, 6, edge_r-wall);
                translate([0,0,-1]) boxZ(W-2*wall-tol-4, D-2*wall-tol-4, 8, edge_r-wall); }
            // TWO mounting rails, 3.75" apart, running front-to-back.
            for(sx=[-1,1])
                translate([sx*rail_gap/2, disp_cy, wall])
                    linear_extrude(rail_h) square([rail_w, rail_len], center=true);
        }
        // Opening under the display for its rear connectors.
        translate([0, disp_cy, -1]) boxZ(rail_gap-rail_w-4, rail_hole_y+6, wall+2, 3);
        // Screw pilot holes down through the rails (4 display corners).
        for(sx=[-1,1],sy=[-1,1])
            translate([sx*rail_gap/2, disp_cy + sy*rail_hole_y/2, -1])
                cylinder(h = wall+rail_h+2, d = disp_screw_d);
        // Speaker dish (flat) + cable hole + grille at the back.
        translate([0, mic_cy, wall-mic_recess_d]) cylinder(h=mic_recess_d+1, d=mic_dia+tol);
        translate([0, mic_cy, -1]) cylinder(h=wall+2, d=mic_cable_d);
        for(ring=[1:4]) for(a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0,mic_cy,-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=wall+2, d=3);
        // Cable slot between display and speaker.
        translate([0, slot_cy, -1]) boxZ(30, 9, wall+2, 4);
    }
}

if(PART=="base") base_tray();
else if(PART=="lid") top_lid();
else { base_tray(); translate([W+30,0,0]) top_lid(); }
