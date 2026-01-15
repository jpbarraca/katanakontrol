// ==========================================================
// PARAMETRIC GUITAR FOOTSWITCH ENCLOSURE - WALLS FIXED
// ==========================================================

/* [General Settings] */
switches_per_row = 4; 
switch_spacing = 45;  
edge_margin = 25;
shell_thickness = 4.0; 
lid_thickness = 5.0;   
corner_radius = 8;     
lip_depth = 2.5;       
lip_width = 2.0;       

/* [LCD & Side Switch Settings] */
lcd_w = 60; lcd_h = 45;
lcd_mount_x_dist = 70; lcd_mount_y_dist = 40; 
lcd_standoff_h = 5;    
lcd_mount_hole_dia = 3.2; 
side_switch_x_dist = 140; 
side_switch_y_offset = 45; 

/* [Component Positioning] */
row_1_y = 35;  row_2_y = 80;  
lcd_y_offset = 45;        

/* [Internal Board Offsets] */
pi_offset = [-45, 10];   
pcb1_offset = [45, 10];  
pcb2_offset = [0, 60];   

/* [Physical Dimensions] */
low_height = 35; high_height = 75; 
depth = 195;      
width = (switches_per_row - 1) * switch_spacing + (edge_margin * 2);

/* [Hardware Diameters] */
switch_hole_dia = 12.5; dc_jack_dia = 11.5;
usb_c_w = 13; usb_c_h = 7;
screw_hole_dia = 3.5; boss_dia = 10;
countersink_dia = 6.5; 
pi_screw_dia = 2.4;    

$fn = 64; 

// --- Computed Values ---
angle = atan((high_height - low_height) / depth);
lid_length = sqrt(pow(depth, 2) + pow(high_height - low_height, 2));

// ==========================================================
// MODULES
// ==========================================================

module screw_boss(h, d_outer, d_inner) {
    difference() {
        cylinder(d=d_outer, h=h);
        translate([0,0,-1]) cylinder(d=d_inner, h=h+2);
    }
}

module rounded_wedge_base(w, d, h_low, h_high, r) {
    hull() {
        translate([r, r, 0]) cylinder(r=r, h=h_low);
        translate([w-r, r, 0]) cylinder(r=r, h=h_low);
        translate([r, d-r, 0]) cylinder(r=r, h=h_high);
        translate([w-r, d-r, 0]) cylinder(r=r, h=h_high);
    }
}

module enclosure_body() {
    // A very large number to ensure cuts extend far beyond the object
    big = width * 10; 

    difference() {
        // 1. BASE GEOMETRY
        rounded_wedge_base(width, depth, low_height, high_height, corner_radius);

        // 2. HOLLOW OUTSIDE
        translate([shell_thickness, shell_thickness, shell_thickness])
            rounded_wedge_base(
                width - shell_thickness*2, depth - shell_thickness*2, 
                low_height + 20, high_height + 20, 
                max(0.1, corner_radius - shell_thickness)
            );

        // 3. REAR PORTS
        translate([width/4, depth + 1, (high_height+low_height)/4]) 
            rotate([90,0,0]) cylinder(d=dc_jack_dia, h=shell_thickness*4, center=true);
        translate([3*width/4, depth + 1, (high_height+low_height)/4]) 
            rotate([90,0,0]) cube([usb_c_w, usb_c_h, shell_thickness*4], center=true);

        // 4. THE GLOBAL TOP TRIM (Fixes the side walls)
        // This cuts everything above the slanted plane of the box
        translate([width/2, 0, low_height]) 
            rotate([angle, 0, 0]) 
            translate([0, big/2, big/2]) 
            cube([big, big, big], center=true);

        // 5. THE LIP RECESSED CUT
        // Cuts the inner shelf 2.5mm deeper than the top edge
        translate([width/2, 0, low_height - lip_depth]) 
            rotate([angle, 0, 0]) 
            translate([0, big/2, big/2]) 
            cube([width - (lip_width*2), big, big], center=true);
    }

    // 6. INTERNAL PILLARS & STANDOFFS
    intersection() {
        // Keeps everything within the outer wedge bounds
        rounded_wedge_base(width, depth, low_height, high_height, corner_radius);
        
        union() {
            // Pillars (shaved by the same slant angle)
            difference() {
                union() {
                    b_off = max(boss_dia/2, corner_radius); 
                    translate([b_off, b_off, 0]) screw_boss(high_height, boss_dia, screw_hole_dia);
                    translate([width - b_off, b_off, 0]) screw_boss(high_height, boss_dia, screw_hole_dia);
                    translate([b_off, depth - b_off, 0]) screw_boss(high_height, boss_dia, screw_hole_dia);
                    translate([width - b_off, depth - b_off, 0]) screw_boss(high_height, boss_dia, screw_hole_dia);

                    pillar_y = (row_1_y + row_2_y) / 2;
                    for (i = [0 : switches_per_row - 2]) {
                        x_pos = edge_margin + (i * switch_spacing) + (switch_spacing / 2);
                        translate([x_pos, pillar_y, 0]) screw_boss(high_height, boss_dia, screw_hole_dia);
                    }
                }
                // Trim pillars to match lid underside
                translate([width/2, 0, low_height - lip_depth]) 
                    rotate([angle, 0, 0]) translate([0, big/2, big/2]) cube([big, big, big], center=true);
            }

            // PCB Standoffs (Floor based)
            translate([width/2 + pi_offset[0], depth/2 + pi_offset[1], shell_thickness])
                for(x=[-29, 29], y=[-11.5, 11.5]) translate([x,y,0]) screw_boss(5, 6, pi_screw_dia);
            for(off = [pcb1_offset, pcb2_offset])
                translate([width/2 + off[0], depth/2 + off[1], shell_thickness])
                    for(x=[-32.5, 32.5], y=[-12.5, 12.5]) translate([x,y,0]) screw_boss(5, 6, pi_screw_dia);
        }
    }
}

module top_lid() {
    lcd_center_y = (lid_length/2) + lcd_y_offset;

    difference() {
        hull() {
            translate([corner_radius, corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([width-corner_radius, corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([corner_radius, lid_length-corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([width-corner_radius, lid_length-corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
        }
        
        // Footswitch holes
        for (i = [0 : switches_per_row - 1]) {
            x_pos = edge_margin + (i * switch_spacing);
            translate([x_pos, row_1_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
            translate([x_pos, row_2_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
        }
        
        // LCD and Side Switches
        translate([width/2 - lcd_w/2, lcd_center_y - lcd_h/2, -1]) cube([lcd_w, lcd_h, lid_thickness + 2]);
        translate([width/2 - side_switch_x_dist/2, lcd_center_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
        translate([width/2 + side_switch_x_dist/2, lcd_center_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);

        // External LCD Mounting Holes with Countersinks
        for(x = [-lcd_mount_x_dist/2, lcd_mount_x_dist/2], y = [-lcd_mount_y_dist/2, lcd_mount_y_dist/2]) {
            translate([width/2 + x, lcd_center_y + y, -1]) {
                cylinder(d=lcd_mount_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=lcd_mount_hole_dia, d2=countersink_dia, h=2);
            }
        }

        // Lid-to-Enclosure Screws
        b_off = max(boss_dia/2, corner_radius);
        l_offset = b_off / cos(angle);
        mid_y = ((row_1_y + row_2_y) / 2) / cos(angle);
        for (p = [[b_off, l_offset], [width-b_off, l_offset], [b_off, lid_length-l_offset], [width-b_off, lid_length-l_offset]]) {
            translate([p[0], p[1], -1]) {
                cylinder(d=screw_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
            }
        }
        for (i = [0 : switches_per_row - 2]) {
            x_pos = edge_margin + (i * switch_spacing) + (switch_spacing / 2);
            translate([x_pos, mid_y, -1]) {
                cylinder(d=screw_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
            }
        }
    }

    // LCD Spacers
    translate([width/2, lcd_center_y, 0]) {
        for(x = [-lcd_mount_x_dist/2, lcd_mount_x_dist/2], y = [-lcd_mount_y_dist/2, lcd_mount_y_dist/2]) {
            translate([x, y, -lcd_standoff_h]) 
                difference() {
                    cylinder(d=6.5, h=lcd_standoff_h);
                    translate([0,0,-1]) cylinder(d=lcd_mount_hole_dia, h=lcd_standoff_h + 2);
                }
        }
    }
}

// --- Render ---
enclosure_body();
translate([width + 25, 0, 0]) top_lid();
