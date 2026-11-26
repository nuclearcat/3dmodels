// SPDX-FileCopyrightText: 2026 Denys Fedoryshchenko
// SPDX-License-Identifier: CC-BY-NC-4.0
// Original source and model geometry: https://creativecommons.org/licenses/by-nc/4.0/
// For commercial use or other licensing terms, contact denys.f@collabora.com.
//
// Juniper Networks EX4500-40F-FB  |  exterior assembly  |  millimeters
// Product names and panel markings identify the depicted switch.
// All trademarks and registered trademarks belong to their respective owners.
//
// Origin: front left bottom of chassis. +X right, +Y rear, +Z up.
// Envelope from Juniper EX4500 Switch Hardware Guide (2017), Table 5.
// Panel layout follows Figs. 4, 6, 9, 10, 16, 17, 18 and 21.
// https://www.andovercg.com/datasheets/juniper-ex4500.pdf
// Front elevation registered to the bare 438.15 x 88.90 mm chassis in figure 9.
// Connector depths, sheet profiles and small hardware remain visual estimates.

/* [Installed hardware] */
// Each installed PIC adds four SFP+ cages.
pic_1_installed = true;
pic_2_installed = true;
// Slot 0 remains populated. Turn off slot 1 to fit its cover.
redundant_ac_supply = true;
rack_brackets = true;

/* [Appearance] */
// Raised panel lettering is also retained in mesh exports.
panel_legends = true;
// Preset camera on opening. Orbit freely in the editor.
initial_view = "Front quarter"; // [Front quarter,Front panel,Rear quarter,Rear panel]

/* [Hidden] */
W = 438.15;
D = 535.94;
H = 88.90;
rack_span = 482.60;
$fn = 24;

skin = "#53595b";
face = "#38434a";
bezel = "#243967";
cover = "#676e70";
nickel = "#aeb5b6";
zinc = "#8d9599";
dark = "#22282a";
shadow = "#141a1c";
ink = "#e5e8df";
green = "#85bf56";
unlit = "#365244";
gold = "#b69855";
glass = "#829674";
lcd_ink = "#263c33";
font = "Liberation Sans:style=Bold";
mono = "Liberation Mono:style=Bold";

front_view = initial_view == "Front panel";
back_view = initial_view == "Rear panel";
$vpt = !$preview ? undef : [W/2, front_view ? 0 : back_view ? D : D*0.44, H/2];
$vpr = !$preview ? undef : front_view ? [90,0,0] : back_view ? [90,0,180] :
       initial_view == "Rear quarter" ? [72,0,204] : [73,0,336];
$vpd = !$preview ? undef : front_view || back_view ? 855 : 1170;

module finish(tint) { color(tint) children(); }

// Panel parts are drawn in local XY as seen by an observer. +Z faces the observer.
module front() { rotate([90,0,0]) children(); }
module rear() { translate([W,D,0]) rotate([0,0,180]) front() children(); }
module slab(bottom, height) {
    translate([0,0,bottom]) linear_extrude(height=height, convexity=12) children();
}
module rr(w,h,r=0.8) {
    translate([r,r]) offset(r=r,$fn=16) square([w-2*r,h-2*r]);
}
module centered_rect(x,y,w,h) { translate([x,y]) square([w,h],center=true); }
module plate(x,y,w,h,bottom,top,tint,r=0.8) {
    finish(tint) translate([x,y]) slab(bottom,top-bottom) rr(w,h,r);
}
module mark(x,y,z,s,sz=2.3,align="center",tint=ink,typeface=font) {
    if(panel_legends) finish(tint) translate([x,y,z-0.04])
        linear_extrude(height=0.16,convexity=8)
            text(s,size=sz,font=typeface,halign=align,valign="center",$fn=12);
}
module pin(x,y,z,r,t,tint) {
    finish(tint) translate([x,y,z]) cylinder(r=r,h=t);
}
module cross_head(x,y,z,d=4.4) {
    finish(nickel) translate([x,y,z-0.1]) difference() {
        cylinder(h=0.85,d1=d,d2=d-0.55);
        translate([0,0,0.51]) rotate(18)
            linear_extrude(height=0.6) union() {
                square([d*0.61,d*0.13],center=true);
                square([d*0.13,d*0.61],center=true);
            }
    }
}
module captive(x,y,z) {
    pin(x,y,z-0.1,3.9,0.75,dark);
    finish(zinc) translate([x,y,z+0.52])
        cylinder(d1=6.8,d2=6.2,h=2.7,$fn=16);
    cross_head(x,y,z+3.17,6);
}
module perforations(x,y,cols,rows,p=4.2,r=1.6) {
    for (j=[0:rows-1], i=[0:cols-1])
        translate([x+p*i+(j%2)*p/2,y+j*p*0.866]) circle(r=r,$fn=6);
}

// Folded enclosure and cover reveal. Thick backing terminates the connector wells.
module enclosure() {
    finish(shadow) translate([0.8,15.5,0.7]) cube([W-1.6,D-29.5,H-1.6]);
    finish(skin) {
        translate([0,0,1.3]) cube([1.6,D,H-2.7]);
        translate([W-1.6,0,1.3]) cube([1.6,D,H-2.7]);
        slab(0,1.65) rr(W,D,1.1);
        slab(H-1.55,1.55) rr(W,D,1.35);
    }
    // A stepped fold catches light at the edge of the removable lid.
    for(x=[0.4,W-1.25]) finish(cover)
        translate([x,2,H-3.9]) cube([0.85,D-4,1.5]);
    for(x=[8,W-8],y=[14,134,268,402,D-14]) lid_screw(x,y);
    for(x=[W/3,2*W/3], y=[12,D-12]) lid_screw(x,y);

    // Shallow pressed manufacturer's mark in the sheet-metal cover.
    if(panel_legends) finish(skin)
        translate([W/2,D*0.52,H-0.08]) linear_extrude(height=0.46)
            text("Juniper",size=30,font="Liberation Sans",halign="center",valign="center");
    for(m=[0,1]) {
        translate([m*W,0,0])
            multmatrix(m==0 ? [[0,0,-1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]]
                            : [[0,0,1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]]) {
                for(ypos=[92,240,388,D-18], h=[8,H-10]) cross_head(ypos,h,0,3.7);
                if(m==0) {
                    plate(D-104,24,34,16,-0.3,0.6,zinc,1.4);
                    for(x=[D-97,D-77]) {
                        pin(x,32,0.45,4.8,1.2,nickel);
                        finish(zinc) translate([x,32,1.35]) cylinder(d=7.7,h=2.6,$fn=6);
                    }
                }
            }
    }
}
module lid_screw(x,y) {
    // Low-profile countersunk lid fasteners.
    pin(x,y,H-0.12,2.5,0.21,dark);
    cross_head(x,y,H+0.08,4.5);
}

module rack_ear() {
    extension=(rack_span-W)/2;
    finish(zinc) {
        translate([0,1,0]) front() slab(-2.0,2.0) difference() {
            translate([-extension,1.6]) rr(extension+0.65,H-3.2,1.45);
            // 19-inch rack center lines, four horizontal clearance slots.
            for(z=[6.35,22.225,66.675,82.55])
                hull() for(dx=[-1.3,1.3]) translate([(W-465.1)/2+dx,z]) circle(d=7.0);
        }
        translate([-1.65,2.3,1.6]) cube([2.05,57,H-3.2]);
    }
    translate([0,1,0]) front() cross_head(-11.0,H/2,0,5.6);
    for(y=[13,47],z=[17,H-17])
        translate([-1.65,y,z]) rotate([0,-90,0]) cross_head(0,0,0,5.2);
}

// Sheet cutouts and module trim are dimensioned in the front X/Z plane.
// Registered to the chassis corners in Hardware Guide, figure 9 (printed p. 25).
// One fixed bank is two columns by two rows, with a single LED strip in the middle.
bank_pitch = 38.12;
pair_pitch = 14.50;
function port_x(i) = 25.0 + floor(i/2)*bank_pitch + (i%2)*pair_pitch;
port_rows = [29.80,14.05];
pic_left = [18.55,181.15];
pic_bottom = 42.65;
pic_width = 150.75;
pic_height = 41.55;
uplink_pitch = 15.28;
function uplink_port(k) = 52.60 + k*uplink_pitch;

module hex_row(x,z,count,step=7.62,r=1.98) {
    for(i=[0:count-1]) translate([x+i*step,z]) circle(r=r,$fn=6);
}
module front_intake() {
    // Outer strips, the narrow column between the PICs, and holes between banks.
    for(j=[0:27])
        hex_row(j%2 ? 9.32 : 5.55,4.50+j*2.12,j%2 ? 1 : 2,7.52);
    for(j=[0:7]) hex_row(175.1,46.85+j*4.22,1);
    for(b=[0:8],j=[0:5])
        hex_row(51.2+b*bank_pitch,11.75+j*4.24,1);
    hex_row(20.35,3.35,51,7.38);
    hex_row(16.75,40.32,50,7.62);
    // Keep solid lands at each printed port number.
    for(i=[0:49]) {
        x=20.55+i*7.62;
        if(min([for(k=[0:19]) abs(x-port_x(k))])>3.60 && abs(x-402.35)>7)
            hex_row(x,38.15,1);
    }
    // The service area is part of the same perforated face. The punched
    // field wraps around the RJ45 shield, USB receptacle and ESD socket.
    for(j=[0:25],i=[0:12]) {
        x=337.35+i*7.62+(j%2)*3.81;
        z=57.75-j*2.16;
        clear_of_ports = z>40.7 || (x>411.5 && z>6.2);
        near_usb = abs(x-417.85)<5.10 && abs(z-16.5)<9.1;
        near_esd = abs(x-428.1)<5.6 && z<19.3;
        if(x<431.0 && clear_of_ports && !near_usb && !near_esd)
            hex_row(x,z,1);
    }
    hex_row(411.00,4.0,3,7.55);
}

module sfp_cage(x,z,surface=0,spacing=14.50) {
    translate([x,z,surface]) {
        w=spacing-0.13;
        finish(nickel) slab(-9.2,10.15) difference() {
            translate([-w/2,-5.03]) rr(w,10.06,0.4);
            translate([-6.83,-4.60]) rr(13.66,9.20,0.28);
        }
        plate(-7.0,-4.75,14,9.50,-9.95,-9.05,shadow,0.25);
        plate(-5.6,-2.35,11.2,1.05,-9.15,-6.15,dark,0.18);
        finish(gold) slab(-6.24,0.13)
            for(i=[0:9]) centered_rect(-4.05+i*0.90,-1.98,0.45,0.52);
        // Rolled spring fingers and a low retaining tab at the cage mouth.
        finish(zinc) slab(0.70,0.32) union() {
            for(dx=[-4.7:0.94:4.7]) centered_rect(dx,4.45,0.40,0.95);
            polygon([[-2.45,-4.78],[2.45,-4.78],[2.08,-3.90],[-2.08,-3.90]]);
        }
    }
}
module socket_centres() {
    for(i=[0:19],z=port_rows) translate([port_x(i),z]) children();
}
module fixed_bank(b) {
    a=port_x(b*2);
    finish(zinc) translate([a-7.94,8.54]) slab(-0.35,0.94) difference() {
        rr(30.25,27.25,0.65);
        for(i=[0:1],z=port_rows) centered_rect(7.94+i*pair_pitch,z-8.54,14.0,9.65);
    }
    // Four alternating light pipes per column belong to the two stacked ports.
    for(i=[0:1]) {
        x=a+i*pair_pitch;
        for(z=port_rows) sfp_cage(x,z,0.52);
        for(k=[0:3]) finish(unlit) translate([x-4.8+3.2*k,21.78,0.55])
            linear_extrude(height=0.28) rotate(k%2==0 ? 180 : 0)
                polygon([[-1.09,-1.17],[1.09,-1.17],[0.39,1.05],[-0.39,1.05]]);
        mark(x,37.95,0,str(4*b+2*i),1.92);
        mark(x,6.55,0,str(4*b+2*i+1),1.92);
    }
}

module rj_shape() {
    polygon([[-6.35,4.65],[6.35,4.65],[6.35,-2.50],[3.45,-2.50],
             [3.45,-3.72],[2.0,-3.72],[2.0,-4.95],[-2.0,-4.95],
             [-2.0,-3.72],[-3.45,-3.72],[-3.45,-2.50],[-6.35,-2.50]]);
}
module rj45(x,z,management=false) {
    translate([x,z,0]) scale([1,management ? 1 : -1,1]) {
        finish(nickel) slab(-8.90,9.85) difference() {
            translate([-7.65,-6.17]) rr(15.3,12.34,0.40);
            rj_shape();
        }
        plate(-7.45,-5.80,14.9,11.6,-9.35,-8.75,shadow,0.4);
        finish(gold) for(i=[0:7]) translate([-3.78+i*1.02,3.25,-8.86])
            rotate([18,0,0]) cube([0.44,0.58,5.50]);
        if(management) for(dx=[-5.6,5.6])
            plate(dx-1.0,-5.40,2.0,1.25,0.90,1.18,unlit,0.20);
    }
}
module usb_vertical(x,z) {
    translate([x,z,0]) rotate(90) {
        finish(nickel) slab(-7.1,8.05) difference() {
            square([14.2,6.35],center=true); square([12.6,4.9],center=true);
        }
        plate(-6.65,-2.65,13.3,5.3,-7.6,-6.95,shadow,0.25);
        plate(-5.55,-1.40,11.1,0.95,-7.1,0.23,dark,0.15);
        finish(gold) slab(-0.15,0.44)
            for(i=[0:3]) centered_rect(-3.6+i*2.4,-1.38,0.65,0.35);
    }
}
module front_plate() {
    finish(face) slab(-1.8,1.8) difference() {
        translate([0.45,0.40]) rr(W-0.90,H-0.80,1.18);
        for(x=pic_left) translate([x,pic_bottom]) rr(pic_width,pic_height,1.65);
        socket_centres() square([14.0,9.65],center=true);
        for(z=[30.0,15.85]) centered_rect(402.35,z,15,11.9);
        centered_rect(417.85,16.50,6.0,13.9);
        translate([428.10,13.80]) circle(d=5.35);
        front_intake();
    }
    for(b=[0:9]) fixed_bank(b);
    finish(zinc) translate([393.8,8.15]) slab(-0.20,0.68) difference() {
        rr(17.15,28.3,0.35);
        for(z=[30.0,15.85]) centered_rect(8.55,z-8.15,15,11.9);
    }
    rj45(402.35,30.0);
    rj45(402.35,15.85,true);
    mark(402.35,38.45,0,"CON",2.0);
    mark(402.35,5.65,0,"MGMT",2.0);
    usb_vertical(417.85,16.5);
    finish(nickel) translate([428.1,13.8]) slab(-5.6,6.60)
        difference(){circle(d=6.40);circle(d=4.50);}
    pin(428.1,13.8,-6.10,2.85,0.66,shadow);
    // ESD marking, placed in the bottom right corner as on the physical face.
    if(panel_legends) finish(ink) translate([431,4.4]) slab(-0.05,0.17)
        difference() {polygon([[-2.8,-1.8],[2.8,-1.8],[0,2.6]]);
                      polygon([[-1.8,-1.25],[1.8,-1.25],[0,1.55]]);}
}

module pic_latch(x,flipped=false) {
    translate([x,0,0]) scale([flipped ? -1 : 1,1,1]) {
        // Folded release bail, top pivot and captive screw in the pull block.
        plate(-14.7,18.1,27.8,21.7,-0.35,1.50,zinc,1.05);
        plate(-13.8,19.0,25.4,16.7,1.35,3.5,nickel,0.70);
        plate(-5.9,18.3,12.5,16.3,3.35,4.85,zinc,0.60);
        pin(0,24.35,4.72,5.45,2.2,nickel);
        cross_head(0,24.35,6.85,9.25);
        // Darkened floor of the cross recess remains legible head-on.
        finish(dark) translate([0,24.35,7.23]) rotate(18)
            linear_extrude(height=0.09) union() {
                square([5.53,1.12],center=true);
                square([1.12,5.53],center=true);
            }
        plate(-13.1,36.1,23.8,2.0,1.40,3.85,nickel,0.30);
        pin(-8.75,38.0,1.30,2.25,2.45,zinc);
    }
}
module uplink(x,populated) {
    translate([x,pic_bottom,0]) {
        finish(shadow) slab(-2.7,2.58) difference() {
            rr(pic_width,pic_height,1.65);
            translate([3.25,3.15]) rr(pic_width-6.50,pic_height-6.30,0.90);
        }
        finish(face) slab(-0.48,1.30) difference() {
            translate([1.5,1.48]) rr(pic_width-3.0,pic_height-2.96,0.85);
            for(j=[0:5]) hex_row(j%2 ? 8.0 : 11.85,5.90+2.13*j,
                                  j%2 ? 18 : 17,7.65,2.0);
            if(populated) for(k=[0:3]) centered_rect(uplink_port(k),25.43,14.50,9.65);
        }
        if(populated) {
            for(k=[0:3]) {
                u=uplink_port(k);
                sfp_cage(u,25.43,0.82,uplink_pitch);
                mark(u,33.77,0.82,str(k),2.15);
                for(dx=[-3.8,3.8]) plate(u+dx-0.92,33.85,1.84,5.40,0.78,1.10,unlit,0.8);
            }
            mark(110.10,34.2,0.82,"ST",2.20);
            plate(117.0,33.85,2.0,5.40,0.78,1.10,green,0.85);
            pic_latch(18.55); pic_latch(132.60,true);
        } else {
            // Molded blank has thick black end grips above its vent field.
            for(u=[2.7,pic_width-28.0]) {
                plate(u,18.15,25.2,20.50,0.60,4.10,dark,1.35);
                plate(u+1.1,19.30,23.0,18.4,4.0,4.75,face,1.05);
            }
        }
    }
}
module keycap(x,z,enter) {
    finish(shadow) translate([x,z,0.7]) scale([1,0.77,1]) cylinder(d=7.8,h=0.65);
    finish(nickel) translate([x,z,1.22]) scale([1,0.77,1])
        cylinder(d1=6.48,d2=5.92,h=0.82);
    if(panel_legends) finish(dark) translate([x,z]) slab(2.00,0.15) {
        if(enter) polygon([[-1.65,-0.18],[-0.45,0.72],[-0.45,0.14],[1.09,0.14],
                           [1.09,1.00],[1.40,1.00],[1.40,-0.27],[-0.45,-0.27],
                           [-0.45,-0.88]]);
        else for(i=[-1:1]) {centered_rect(0.35,i*0.65,1.9,0.21);
                              translate([-1.2,i*0.65]) circle(r=0.15,$fn=8);}
    }
}
module operator_panel() {
    plate(336.0,60.50,96.32,24.25,-0.16,0.75,bezel,1.12);
    if(panel_legends) finish(ink) translate([338.7,75.9,0.70])
        linear_extrude(height=0.17) resize([23.65,5.65])
            text("juniper",size=7,font="Liberation Sans",valign="bottom",$fn=12);
    mark(360.9,75.45,0.75,"NETWORKS",1.12,"right");
    mark(338.9,66.65,0.75,"EX4500",2.45,"left");
    plate(362.55,66.34,39.05,13.36,0.61,1.28,dark,0.55);
    plate(363.46,67.23,37.23,11.58,1.17,1.45,glass,0.34);
    mark(365.0,75.71,1.45,"00 RE EX4500",1.98,"left",lcd_ink,mono);
    mark(365.0,70.38,1.45,"SPD  ALARMS 00",1.98,"left",lcd_ink,mono);
    keycap(409.1,75.96,false);
    keycap(409.1,68.16,true);
    for(i=[0:2]) {
        z=79.05-3.76*i;
        pin(416.13,z,0.67,1.36,0.36,shadow);
        pin(416.13,z,0.99,0.93,0.24,i==0 ? unlit : green);
        mark(418.4,z,0.75,["ALM","SYS","MST"][i],1.87,"left");
    }
}

module rear_frame() {
    finish(face) slab(-2.25,2.25) difference() {
        translate([0.65,0.75]) rr(W-1.3,H-1.55,1.4);
        for(y=[3.5,45.5]) translate([4.6,y]) rr(108.6,39.1,1.4);
        translate([118.8,3.3]) rr(314.8,49.7,1.4);
        translate([118.8,55.4]) rr(314.8,29.7,1.4);
    }
    for(x=[2.9,W-3.0],y=[3.6,H-3.4]) cross_head(x,y,0,3.5);
}

// Axial impeller sits behind the perforations on a recessed motor support.
module rotor(x,y,r,depth) {
    translate([x,y]) {
        finish(dark) slab(depth-2.5,2.65) union() {
            difference() {circle(r=r); circle(r=r-1.1);}
            for(a=[0:45:315]) rotate(a) translate([-0.78,0]) square([1.56,r-0.55]);
        }
        finish(shadow) slab(depth-0.4,1.20) union() {
            circle(r=r*0.33);
            for(a=[0:360/7:359]) rotate(a) scale([r,r])
                polygon([[0.03,0.25],[0.26,0.23],[0.60,0.48],[0.80,0.53],
                         [0.69,0.68],[0.39,0.82],[0.30,0.67],[0.28,0.48]]);
        }
        pin(0,0,depth+0.68,r*0.27,0.5,dark);
    }
}
module arch_handle(x,y,z,height,reach,r,tint) {
    // Bent wire extraction handle with a straight handgrip and swept bends.
    path=[[0,0,-0.4],[0,0,reach-2.4],[0,1.0,reach-0.7],
          [0,2.8,reach],[0,height-2.8,reach],[0,height-1.0,reach-0.7],
          [0,height,reach-2.4],[0,height,-0.4]];
    finish(tint) translate([x,y,z]) for(i=[0:len(path)-2])
        hull() for(j=[i,i+1]) translate(path[j]) sphere(r=r,$fn=12);
}
module fan_cartridge() {
    translate([118,2.6]) {
        finish(cover) slab(-1.15,2.15) difference() {
            rr(316.5,51.1,1.45);
            perforations(19.0,6.4,70,11,4.0,1.76);
        }
        // Rear wall remains visible through real holes between the five rotors.
        for(i=[0:4]) rotor(47.5+i*55.1,25.1,22,-7.2);
        for(i=[0:4]) {
            // Short rear bosses tie the rotor supports to the chassis backing.
            pin(47.5+i*55.1,25.1,-14.1,3.5,5.1,dark);
        }
        for(x=[8.2,308.3]) {
            plate(x-4.6,7.0,9.2,37,-0.1,2.0,dark,1.45);
            arch_handle(x,10.6,1.65,29.5,9.0,2.05,zinc);
            for(y=[4,47.0]) cross_head(x,y,0.98,3.4);
        }
        plate(132,39.0,50,8.4,0.88,1.22,green,0.7);
        mark(154.6,43.25,1.22,"EXHAUST",2.8,"center",dark);
        if(panel_legends) finish(dark) slab(1.18,0.16)
            polygon([[168.4,41.6],[171.6,43.25],[168.4,44.9]]);
    }
}
module intraconnect() {
    translate([118.0,54.8]) {
        finish(cover) slab(-1.15,2.15) difference() {
            rr(316.5,30.9,1.35);
            perforations(19,6.15,45,6,4,1.68);
        }
        for(x=[7.5,308.7]) captive(x,15.5,1.0);
        mark(211.0,17.7,1.0,"Juniper",5.3,"left",ink,"Liberation Sans");
        mark(211.4,11.1,1.0,"NETWORKS",2.05,"left");
        mark(293,18.2,1.0,"EX4500-LB",3.45,"right");
        pin(289.8,10.0,0.93,1.15,0.42,green);
        mark(286.1,10.0,1.0,"ST",2.0,"right");
    }
}

module inlet_profile() {
    polygon([[-11.1,-7.3],[11.1,-7.3],[11.1,3.5],[7.6,7.3],
             [-7.6,7.3],[-11.1,3.5]]);
}
module ac_inlet(x,y) {
    translate([x,y]) {
        finish(dark) slab(-8.9,10.85) difference() {
            translate([-14.2,-10.35]) rr(28.4,20.7,2.2);
            inlet_profile();
        }
        finish(shadow) slab(-10,1.45) offset(delta=0.5) inlet_profile();
        finish(nickel) for(p=[[-6.4,-2.65],[6.4,-2.65],[0,3.15]])
            translate([p[0]-2.05,p[1]-0.74,-8.85]) cube([4.1,1.48,8.35]);
    }
}
module ac_supply(y,slot,populated) {
    translate([3.9,y]) {
        finish(populated?zinc:cover) slab(-1.2,2.12) difference() {
            rr(110.0,40.5,1.45);
            if(populated) {
                centered_rect(26,21,27.5,19.9);
                intersection() {
                    translate([78.2,20.25]) circle(d=35.6,$fn=48);
                    perforations(58.0,1.0,12,12,3.45,1.45);
                }
            }
        }
        if(populated) {
            ac_inlet(26,21);
            rotor(78.2,20.25,17,-6.1);
            pin(78.2,20.25,-14.1,4.2,5.9,dark);
            for(dx=[-15.5,15.5],dy=[-15.3,15.3])
                cross_head(78.2+dx,20.25+dy,0.92,3.1);
            arch_handle(48.2,7.2,0.8,25.0,14.8,1.75,nickel);
            plate(3.6,8.5,5.1,24,0.78,2.65,green,1.25);
            for(k=[0:3]) plate(4.05,13.9+2.8*k,4.2,1.0,2.54,3.13,green,0.18);
            mark(25.9,35.8,0.92,"AC INPUT",2.35);
            pin(17,6.6,0.86,1.32,0.45,green);
            mark(20.0,6.6,0.92,"AC OK",2.0,"left");
        } else {
            for(x=[9,100.5]) captive(x,20.3,0.92);
        }
        mark(104,20.3,0.92,str(slot),3.4);
    }
}

module ex4500() {
    enclosure();
    if(rack_brackets) {
        rack_ear();
        translate([W,0,0]) mirror([1,0,0]) rack_ear();
    }
    front() {
        front_plate();
        uplink(pic_left[0],pic_1_installed);
        uplink(pic_left[1],pic_2_installed);
        operator_panel();
    }
    rear() {
        rear_frame();
        ac_supply(2.8,0,true);
        ac_supply(44.8,1,redundant_ac_supply);
        fan_cartridge();
        intraconnect();
    }
}

ex4500();
