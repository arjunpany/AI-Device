// ============================================================================
//  AI Lecture Note-Taker — matches the cardboard prototype
//    * Desk box you look down at
//    * DISPLAY flat on the top, front half, facing up
//    * ReSpeaker flat on the top, back half, SAME level (no raised step)
//    * Raspberry Pi inside on the floor, under the display
//    * PORT HOLES: USB + Ethernet out the FRONT wall (below the screen);
//                  USB-C power + HDMI out the LEFT wall
//    * Two parts: BASE tray + TOP lid (lid lifts off)
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
// ============================================================================

PART = "both";
$fn = 64;

// --- measured parts -------------------------------------------------------
disp_w=120.7; disp_h=74.7; disp_thick=5;         // 4.75 x 2.94 in
screen_w=109; screen_h=61;
disp_hole_dx=111; disp_hole_dy=65; disp_screw_d=2.8;   // VERIFY spacing
mic_dia=70; mic_recess_d=3; mic_cable_d=12;      // 7 cm
pi_w=88.9; pi_h=57.2;                             // 3.5 x 2.25 in Pi 4
pi_hole_dx=58; pi_hole_dy=49; pi_standoff_h=4; pi_screw_d=2.5;

// --- build ----------------------------------------------------------------
wall=3; tol=0.4; margin=8; gap=12; edge_r=8;
inner_h=40;                                       // tall enough for Pi + display cables
W = disp_w + 2*margin;                            // ~137
D = disp_h + gap + mic_dia + 2*margin;            // ~171

disp_cy = -D/2 + margin + disp_h/2;               // screen on the front half
mic_cy  =  D/2 - margin - mic_dia/2;              // speaker on the back half (FLAT)
slot_cy = disp_cy + disp_h/2 + 8;                 // mic-cable slot behind the screen

// Pi rotated so its short (USB/LAN) edge faces the FRONT and its long
// (power/HDMI) edge faces the LEFT. Placed toward the front, under the screen.
span_x = pi_h;  span_y = pi_w;                    // Pi footprint in the case
hole_x = pi_hole_dy; hole_y = pi_hole_dx;
pi_cx = 0;
pi_cy = -D/2 + wall + margin + span_y/2;

// --- Pi 4 port holes ------------------------------------------------------
flip_front = false;   // flip if the USB/Ethernet row is mirrored
flip_left  = false;   // flip if the power/HDMI row is mirrored
port_z = wall + pi_standoff_h + 6;
front_ports = [ [10.5,17,15],[29.0,16,18],[47.0,16,18] ];        // LAN,USB,USB (along X)
left_ports  = [ [ 7.7,12,8],[26.0,9,8],[39.5,9,8],[54.0,9,9] ];  // USBC,HDMI,HDMI,AV (along Y)

// --- helpers --------------------------------------------------------------
module boxZ(w,d,h,r){ linear_extrude(h) offset(r=r) offset(delta=-r)
    square([w,d],center=true); }
module post(h,od,hd){ difference(){ cylinder(h=h,d=od);
    translate([0,0,1.5]) cylinder(h=h,d=hd);} }
module cut_front(){
    for(p=front_ports){
        x = flip_front ? pi_cx+span_x/2-p[0] : pi_cx-span_x/2+p[0];
        translate([x, -D/2 + wall/2, port_z]) cube([p[1], wall*3, p[2]], center=true);
    }
}
module cut_left(){
    for(p=left_ports){
        y = flip_left ? pi_cy+span_y/2-p[0] : pi_cy-span_y/2+p[0];
        translate([-W/2 + wall/2, y, port_z]) cube([wall*3, p[1], p[2]], center=true);
    }
}

// --- base tray ------------------------------------------------------------
module base_tray(){
    union(){
        difference(){
            boxZ(W, D, inner_h+wall, edge_r);
            translate([0,0,wall]) boxZ(W-2*wall, D-2*wall, inner_h+1, edge_r-wall);
            cut_front();
            cut_left();
        }
        translate([pi_cx, pi_cy, wall])
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*hole_x/2, sy*hole_y/2, 0])
                    post(pi_standoff_h, 6, pi_screw_d);
    }
}

// --- top lid --------------------------------------------------------------
module top_lid(){
    difference(){
        union(){
            boxZ(W, D, wall, edge_r);                        // top plate
            translate([0,0,-6])                              // rim into base
                difference(){ boxZ(W-2*wall-tol, D-2*wall-tol, 6, edge_r-wall);
                    translate([0,0,-1]) boxZ(W-2*wall-tol-4, D-2*wall-tol-4, 8, edge_r-wall); }
            if(disp_hole_dx>0)
                translate([0, disp_cy, -(disp_thick+2)])
                    for(sx=[-1,1],sy=[-1,1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2, 0])
                            post(disp_thick+2, 7, disp_screw_d);
        }
        // Screen opening (front, facing up).
        translate([0, disp_cy, -1]) boxZ(screen_w, screen_h, wall+2, 3);
        // Speaker dish FLAT in the plate (back) + cable hole + grille.
        translate([0, mic_cy, wall-mic_recess_d]) cylinder(h=mic_recess_d+1, d=mic_dia+tol);
        translate([0, mic_cy, -1]) cylinder(h=wall+2, d=mic_cable_d);
        for(ring=[1:4]) for(a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0,mic_cy,-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=wall+2, d=3);
        // Cable slot between screen and speaker.
        translate([0, slot_cy, -1]) boxZ(30, 9, wall+2, 4);
    }
}

// --- render ---------------------------------------------------------------
if(PART=="base") base_tray();
else if(PART=="lid") top_lid();
else { base_tray(); translate([W+20,0,0]) top_lid(); }
