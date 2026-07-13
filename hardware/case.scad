// ============================================================================
//  AI Lecture Note-Taker — screen head + uniform narrow body
//    * WIDE only at the screen (a short head just big enough for the display)
//    * Everything below is ONE narrow width you hold
//    * Speaker + Pi live in the narrow body (Pi rotated to fit the width)
//    * Screen screws to posts attached to the lid
//
//  EXPORT:  PART="base" -> F6 -> Export STL ;  PART="lid" -> F6 -> Export STL
// ============================================================================

PART = "both";
$fn = 64;

// --- measured parts -------------------------------------------------------
disp_w=120.7; disp_h=74.7; disp_thick=5;      // 4.75 x 2.94 in
screen_w=109; screen_h=61;
disp_hole_dx=111; disp_hole_dy=65; disp_screw_d=2.8;   // VERIFY spacing
mic_dia=70; mic_recess_d=3; mic_cable_d=12;    // 7 cm
pi_w=88.9; pi_h=57.2;                           // 3.5 x 2.25 in (long, short)
pi_hole_dx=58; pi_hole_dy=49; pi_standoff_h=3; pi_screw_d=2.5;

// --- build ----------------------------------------------------------------
wall=2.6; tol=0.4; margin=7; grip_r=14;
disp_back_clear=16; pi_tall=18;
inner_h = max(pi_tall, disp_back_clear) + pi_standoff_h + 3;

// --- footprint: short WIDE screen head, then a uniform NARROW body --------
head_w = disp_w + 2*margin;    // ~135 (wide, screen only)
head_d = disp_h + 2*margin;    // ~89  (just the screen depth)
body_w = mic_dia + 2*margin;   // ~84  (the single narrow width for everything else)
body_d = pi_w + 2*margin + 10; // ~113 (fits the rotated Pi + a little grip)

outer_w = head_w;
outer_d = head_d + body_d;
head_cy = -outer_d/2 + head_d/2;      // screen head at the FRONT (-Y)
body_cy =  outer_d/2 - body_d/2;      // narrow body behind it

disp_cy = head_cy;
// Speaker sits just below the screen; Pi fills the body under it/the grip.
mic_cy  = -outer_d/2 + head_d + margin + mic_dia/2;
pi_cx   = 0;
pi_cy   = body_cy;
slot_cy = -outer_d/2 + head_d;        // cable slot at the waist

// --- Pi 4 ports (Pi ROTATED 90 deg to fit the narrow body) ----------------
// Long HDMI/power edge now runs top-to-bottom -> faces the RIGHT (+X) wall.
// Short USB/Ethernet edge runs across -> faces the far BOTTOM (+Y) end wall.
flip_right = false;   // flip if the HDMI/power row is mirrored
flip_end   = false;   // flip if the USB/Ethernet row is mirrored
port_z = wall + pi_standoff_h + 5;
// rotated: Pi spans pi_h in X and pi_w in Y; hole spacing swaps too.
pi_span_x = pi_h;  pi_span_y = pi_w;
hole_x = pi_hole_dy;  hole_y = pi_hole_dx;
right_ports = [ [ 7.7,12,8],[26.0,9,8],[39.5,9,8],[54.0,9,9] ]; // USBC,HDMI,HDMI,AV (along Y)
end_ports   = [ [10.5,17,15],[29.0,16,18],[47.0,16,18] ];        // LAN,USB,USB (along X)

// --- helpers --------------------------------------------------------------
module outline2d(inset){
    offset(delta=-inset) offset(r=grip_r) offset(delta=-grip_r)
        union(){
            translate([0,head_cy]) square([head_w,head_d],center=true);
            translate([0,body_cy]) square([body_w,body_d],center=true);
        }
}
module post(h,od,hd){ difference(){ cylinder(h=h,d=od);
    translate([0,0,1.5]) cylinder(h=h,d=hd);} }
module rrect_hole(w,h,d,r){ linear_extrude(d) offset(r=r) offset(delta=-r)
    square([w,h],center=true); }

module cut_right_ports(){   // +X wall, offsets along Y (Pi's long edge)
    for(p=right_ports){
        y = flip_right ? pi_cy + pi_span_y/2 - p[0] : pi_cy - pi_span_y/2 + p[0];
        translate([body_w/2 - wall/2, y, port_z])
            cube([wall*2+2, p[1], p[2]], center=true);
    }
}
module cut_end_ports(){     // +Y (bottom) wall, offsets along X (Pi's short edge)
    for(p=end_ports){
        x = flip_end ? pi_cx + pi_span_x/2 - p[0] : pi_cx - pi_span_x/2 + p[0];
        translate([x, outer_d/2 - wall/2, port_z])
            cube([p[1], wall*2+2, p[2]], center=true);
    }
}

// --- base tray ------------------------------------------------------------
module base_tray(){
    union(){
        difference(){
            linear_extrude(inner_h+wall) outline2d(0);
            translate([0,0,wall]) linear_extrude(inner_h+1) outline2d(wall);
            cut_right_ports();
            cut_end_ports();
        }
        // Pi cradle in the body (rotated).
        translate([pi_cx, pi_cy, wall]){
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*hole_x/2, sy*hole_y/2, 0])
                    post(pi_standoff_h,6,pi_screw_d);
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*(pi_span_x/2+tol), sy*(pi_span_y/2+tol),0])
                    for(d=[[-sx*3,0,1.6,8],[0,-sy*3,8,1.6]])
                        translate([d[0],d[1],0])
                            cube([d[2],d[3],pi_standoff_h+5],center=true);
        }
    }
}

// --- top lid --------------------------------------------------------------
module top_lid(){
    difference(){
        union(){
            linear_extrude(wall) outline2d(0);
            translate([0,0,-6]) linear_extrude(6)
                difference(){ outline2d(wall+tol); offset(delta=-2.4) outline2d(wall+tol); }
            if(disp_hole_dx>0)
                translate([0,disp_cy,-(disp_thick+2)])
                    for(sx=[-1,1],sy=[-1,1])
                        translate([sx*disp_hole_dx/2, sy*disp_hole_dy/2,0])
                            post(disp_thick+2,7,disp_screw_d);
        }
        translate([0,disp_cy,-1]) rrect_hole(screen_w,screen_h,wall+2,3);
        translate([0,mic_cy,wall-mic_recess_d]) cylinder(h=mic_recess_d+1,d=mic_dia+tol);
        translate([0,mic_cy,-1]) cylinder(h=wall+2,d=mic_cable_d);
        for(ring=[1:4]) for(a=[0:360/(ring*6):359])
            rotate([0,0,a]) translate([0,mic_cy,-1])
                translate([ring*(mic_dia/2/5),0,0]) cylinder(h=wall+2,d=3);
        translate([0,slot_cy,-1]) rrect_hole(30,9,wall+2,4);
    }
}

// --- render ---------------------------------------------------------------
if(PART=="base") base_tray();
else if(PART=="lid") top_lid();
else { base_tray(); translate([outer_w+20,0,0]) top_lid(); }
