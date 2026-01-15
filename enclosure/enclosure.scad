// ==========================================================
// PARAMETRIC GUITAR FOOTSWITCH ENCLOSURE - TOP-MOUNT LCD
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
lcd_mount_hole_dia = 3.2; // Diameter for LCD mounting screws (e.g. M3)
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
// Angle of the slant: $angle = \arctan\left(\frac{high\_height - low\_height}{depth}\right)$
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
    difference() {
        rounded_wedge_base(width, depth, low_height, high_height, corner_radius);

        translate([shell_thickness, shell_thickness, shell_thickness])
            rounded_wedge_base(
                width - shell_thickness*2, depth - shell_thickness*2, 
                low_height + 10, high_height + 10, 
                max(0.1, corner_radius - shell_thickness)
            );

        // Rear Connectivity
        translate([width/4, depth + 1, (high_height+low_height)/4]) 
            rotate([90,0,0]) cylinder(d=dc_jack_dia, h=shell_thickness*4, center=true);
        translate([3*width/4, depth + 1, (high_height+low_height)/4]) 
            rotate([90,0,0]) cube([usb_c_w, usb_c_h, shell_thickness*4], center=true);
            
        // Slant Cut for Lip
        translate([0, 0, low_height - lip_depth]) 
            rotate([angle, 0, 0]) 
            translate([lip_width, 0, 0]) 
            cube([width - (lip_width*2), depth * 2, high_height]);
        
        // Final trim for wall tops
        translate([0,0, low_height]) rotate([angle, 0, 0])
            translate([-50, -50, 0]) cube([width+100, depth*2, 100]);
    }

    intersection() {
        rounded_wedge_base(width, depth, low_height, high_height, corner_radius);
        union() {
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
                translate([0, 0, low_height - lip_depth]) 
                    rotate([angle, 0, 0]) translate([-50, -50, 0]) cube([width+100, depth*2, high_height]);
            }
            // Floor Standoffs for Internal Boards
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
        
        // 1. Footswitch Holes
        for (i = [0 : switches_per_row - 1]) {
            x_pos = edge_margin + (i * switch_spacing);
            translate([x_pos, row_1_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
            translate([x_pos, row_2_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
        }
        
        // 2. LCD Main Cutout
        translate([width/2 - lcd_w/2, lcd_center_y - lcd_h/2, -1]) cube([lcd_w, lcd_h, lid_thickness + 2]);

        // 3. Side Switch Holes
        translate([width/2 - side_switch_x_dist/2, lcd_center_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
        translate([width/2 + side_switch_x_dist/2, lcd_center_y, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);

        // 4. LCD EXTERNAL MOUNTING HOLES (New)
        for(x = [-lcd_mount_x_dist/2, lcd_mount_x_dist/2], y = [-lcd_mount_y_dist/2, lcd_mount_y_dist/2]) {
            translate([width/2 + x, lcd_center_y + y, -1]) {
                cylinder(d=lcd_mount_hole_dia, h=lid_thickness + 2);
                // Countersink for the LCD screws
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=lcd_mount_hole_dia, d2=countersink_dia, h=2);
            }
        }

        // 5. Lid-to-Enclosure Mounting Holes
        b_off = max(boss_dia/2, corner_radius);
        l_offset = b_off / cos(angle);
        mid_y = ((row_1_y + row_2_y) / 2) / cos(angle);
        mount_points = [[b_off, l_offset], [width-b_off, l_offset], [b_off, lid_length-l_offset], [width-b_off, lid_length-l_offset]];
        for (p = mount_points) translate([p[0], p[1], -1]) {
            cylinder(d=screw_hole_dia, h=lid_thickness + 2);
            translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
        }
        for (i = [0 : switches_per_row - 2]) {
            x_pos = edge_margin + (i * switch_spacing) + (switch_spacing / 2);
            translate([x_pos, mid_y, -1]) {
                cylinder(d=screw_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
            }
        }
    }

    // LCD UNDERSIDE SPACERS (Now with through-holes)
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
