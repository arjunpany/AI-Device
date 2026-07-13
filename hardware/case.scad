// ============================================================================
//  AI Lecture Note-Taker — 8 x 4 x 2 inch desk box (matches the prototype)
//    * Fixed outer size: 8" long (D) x 4" wide (W) x 2" tall (H)
//    * DISPLAY flat on top, rotated 90 deg (long side runs down the length)
//      so it fits the 4" width; front half, facing up
//    * ReSpeaker flat on top, back half, same level
//    * Pi inside on the floor under the display
//    * Ports: USB + Ethernet out the FRONT; USB-C power + HDMI out the LEFT
//    * Two parts: BASE tray + TOP lid
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
// ============================================================================

PART = "both";
$fn = 64;

// --- fixed outer size (inches -> mm) --------------------------------------
in = 25.4;
W = 4*in;      // 101.6  width
D = 8*in;      // 203.2  length
H = 2*in;      // 50.8   height
wall = 3; tol = 0.4; margin = 6; edge_r = 8;
inner_h = H - 2*wall;                 // 44.8 interior

// --- parts ----------------------------------------------------------------
// display, rotated 90 deg: long side (120.7) along the length D, short (74.7)
// across the width W.
disp_x = 74.7;  disp_y = 120.7;
screen_x = 61;  screen_y = 109;
dhole_x = 65;   dhole_y = 111;        // display screw-hole spacing (VERIFY)
disp_screw_d = 2.8; disp_thick = 5;

mic_dia = 70; mic_recess_d = 3; mic_cable_d = 12;

// Pi 4, rotated: short (USB/LAN) edge faces FRONT, long (HDMI) edge faces LEFT.
pi_w = 88.9; pi_h = 57.2; pi_hole_dx = 58; pi_hole_dy = 49;
pi_standoff_h = 4; pi_screw_d = 2.5;
span_x = pi_h; span_y = pi_w; hole_x = pi_hole_dy; hole_y = pi_hole_dx;

// --- placement ------------------------------------------------------------
disp_cy = -D/2 + margin + disp_y/2;           // display toward the FRONT
mic_cy  =  D/2 - margin - mic_dia/2;           // speaker toward the BACK
slot_cy = (disp_cy + disp_y/2 + mic_cy - mic_dia/2)/2;
pi_cx = 0;
pi_cy = -D/2 + wall + margin + span_y/2;

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

// --- top lid --------------------------------------------------------------
module top_lid(){
    difference(){
        union(){
            boxZ(W, D, wall, edge_r);
            translate([0,0,-6]) difference(){
                boxZ(W-2*wall-tol, D-2*wall-tol, 6, edge_r-wall);
                translate([0,0,-1]) boxZ(W-2*wall-tol-4, D-2*wall-tol-4, 8, edge_r-wall); }
            if(dhole_x>0) translate([0, disp_cy, -(disp_thick+2)])
                for(sx=[-1,1],sy=[-1,1])
                    translate([sx*dhole_x/2, sy*dhole_y/2, 0]) post(disp_thick+2,7,disp_screw_d);
        }
        translate([0, disp_cy, -1]) boxZ(screen_x, screen_y, wall+2, 3);   // screen opening
        translate([0, mic_cy, wall-mic_recess_d]) cylinder(h=mic_recess_d+1, d=mic_dia+tol);
        translate([0, mic_cy, -1]) cylinder(h=wall+2, d=mic_cable_d);
        for(ring=[1:4]) for(a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0,mic_cy,-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=wall+2, d=3);
        translate([0, slot_cy, -1]) boxZ(30, 9, wall+2, 4);                // cable slot
    }
}

if(PART=="base") base_tray();
else if(PART=="lid") top_lid();
else { base_tray(); translate([W+20,0,0]) top_lid(); }
