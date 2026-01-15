// ==========================================================
// PARAMETRIC GUITAR FOOTSWITCH ENCLOSURE
// ==========================================================

/* [General Settings] */
switches_per_row = 4; 
switch_spacing = 45;  
edge_margin = 25;
shell_thickness = 4.5; 
lid_thickness = 5.0;   
corner_radius = 8;     

/* [LCD Display Settings] */
lcd_w = 60;
lcd_h = 45;
lcd_mount_x_dist = 70; 
lcd_mount_y_dist = 40; 
lcd_standoff_h = 5;    

/* [Component Positioning] */
row_1_y_position = 35;  
row_2_y_position = 80;  
lcd_y_offset = 45;       

// Side Switches (Beside LCD)
side_switch_x_dist = 110; // Total distance between the two side switches
side_switch_y_offset = 45; // Vertical alignment (usually same as lcd_y_offset)

/* [Internal Board Offsets] */
pi_offset = [-45, 10];   
pcb1_offset = [45, 10];  
pcb2_offset = [0, 60];   

/* [Physical Dimensions] */
low_height = 35;
high_height = 75; 
depth = 195;      
width = (switches_per_row - 1) * switch_spacing + (edge_margin * 2);

/* [Hardware Diameters] */
switch_hole_dia = 12.5; 
dc_jack_dia = 11.5;
usb_c_w = 13;
usb_c_h = 7;
screw_hole_dia = 3.5;  
countersink_dia = 6.5; 
boss_dia = 10;
pi_screw_dia = 2.4;    
lcd_mount_hole_dia = 2.5; 

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

module rounded_wedge(w, d, h_low, h_high, r) {
    hull() {
        translate([r, r, 0]) cylinder(r=r, h=h_low);
        translate([w-r, r, 0]) cylinder(r=r, h=h_low);
        translate([r, d-r, 0]) cylinder(r=r, h=h_high);
        translate([w-r, d-r, 0]) cylinder(r=r, h=h_high);
    }
}

module enclosure_body() {
    difference() {
        rounded_wedge(width, depth, low_height, high_height, corner_radius);
        
        translate([shell_thickness, shell_thickness, shell_thickness])
            rounded_wedge(width - shell_thickness*2, depth - shell_thickness*2, low_height + 10, high_height + 10, max(0.1, corner_radius - shell_thickness));
        
        // Rear Connectivity
        translate([width/4, depth + 1, high_height/2]) rotate([90,0,0]) cylinder(d=dc_jack_dia, h=shell_thickness*4, center=true);
        translate([3*width/4, depth + 1, high_height/2]) rotate([90,0,0]) cube([usb_c_w, usb_c_h, shell_thickness*4], center=true);

        // Ventilation Slats
        for(z = [shell_thickness + 12 : 10 : high_height - 15]) {
            translate([-1, depth/2, z]) cube([width+2, 18, 4]);
        }

        // Bottom Rubber Foot Pads
        for(x=[15, width-15], y=[15, depth-15])
            translate([x, y, -0.5]) cylinder(d=12, h=2);
    }
    
    b_off = max(boss_dia/2, corner_radius); 
    translate([b_off, b_off, 0]) screw_boss(low_height - 2, boss_dia, screw_hole_dia);
    translate([width - b_off, b_off, 0]) screw_boss(low_height - 2, boss_dia, screw_hole_dia);
    translate([b_off, depth - b_off, 0]) screw_boss(high_height - 2, boss_dia, screw_hole_dia);
    translate([width - b_off, depth - b_off, 0]) screw_boss(high_height - 2, boss_dia, screw_hole_dia);

    // Structural Pillars
    pillar_y = (row_1_y_position + row_2_y_position) / 2;
    pillar_h = low_height + (high_height - low_height) * (pillar_y / depth);
    for (i = [0 : switches_per_row - 2]) {
        x_pos = edge_margin + (i * switch_spacing) + (switch_spacing / 2);
        translate([x_pos, pillar_y, 0]) screw_boss(pillar_h - 2, boss_dia, screw_hole_dia);
    }

    // Board Standoffs
    translate([width/2 + pi_offset[0], depth/2 + pi_offset[1], shell_thickness])
        for(x=[-29, 29], y=[-11.5, 11.5]) translate([x,y,0]) screw_boss(5, 6, pi_screw_dia);

    for(off = [pcb1_offset, pcb2_offset])
        translate([width/2 + off[0], depth/2 + off[1], shell_thickness])
            for(x=[-32.5, 32.5], y=[-12.5, 12.5]) translate([x,y,0]) screw_boss(5, 6, pi_screw_dia);
}

module top_lid() {
    difference() {
        hull() {
            translate([corner_radius, corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([width-corner_radius, corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([corner_radius, lid_length-corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
            translate([width-corner_radius, lid_length-corner_radius, 0]) cylinder(r=corner_radius, h=lid_thickness);
        }
        
        // LCD Window
        translate([width/2 - lcd_w/2, (lid_length/2 - lcd_h/2) + lcd_y_offset, -1]) 
            cube([lcd_w, lcd_h, lid_thickness + 2]);
            
        // MAIN SWITCH ROWS
        for (i = [0 : switches_per_row - 1]) {
            x_pos = edge_margin + (i * switch_spacing);
            translate([x_pos, row_1_y_position, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
            translate([x_pos, row_2_y_position, -1]) cylinder(d=switch_hole_dia, h=lid_thickness + 2);
            
            translate([x_pos, row_1_y_position + 15, lid_thickness - 1])
                linear_extrude(2) text(str(i+1), size=5, halign="center", font="Arial:style=Bold");
            translate([x_pos, row_2_y_position + 15, lid_thickness - 1])
                linear_extrude(2) text(str(i+switches_per_row+1), size=5, halign="center", font="Arial:style=Bold");
        }

        // SIDE SWITCHES (L/R of LCD)
        side_sw_y_lid = (lid_length/2) + side_switch_y_offset;
        translate([width/2 - side_switch_x_dist/2, side_sw_y_lid, -1])
            cylinder(d=switch_hole_dia, h=lid_thickness+2);
        translate([width/2 + side_switch_x_dist/2, side_sw_y_lid, -1])
            cylinder(d=switch_hole_dia, h=lid_thickness+2);

        // Mounting Holes
        b_off = max(boss_dia/2, corner_radius);
        l_offset = b_off / cos(angle);
        lid_pillar_y = ((row_1_y_position + row_2_y_position) / 2) / cos(angle);
        
        for (p = [[b_off, l_offset], [width-b_off, l_offset], [b_off, lid_length-l_offset], [width-b_off, lid_length-l_offset]]) {
            translate([p[0], p[1], -1]) {
                cylinder(d=screw_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
            }
        }
        for (i = [0 : switches_per_row - 2]) {
            x_pos = edge_margin + (i * switch_spacing) + (switch_spacing / 2);
            translate([x_pos, lid_pillar_y, -1]) {
                cylinder(d=screw_hole_dia, h=lid_thickness + 2);
                translate([0,0, lid_thickness - 1.5]) cylinder(d1=screw_hole_dia, d2=countersink_dia, h=2.5);
            }
        }
    }

    // LCD Mounting Standoffs
    translate([width/2, (lid_length/2) + lcd_y_offset, 0]) {
        for(x = [-lcd_mount_x_dist/2, lcd_mount_x_dist/2], y = [-lcd_mount_y_dist/2, lcd_mount_y_dist/2]) {
            translate([x, y, -lcd_standoff_h]) 
                screw_boss(lcd_standoff_h, 6, lcd_mount_hole_dia);
        }
    }
}

// --- Render ---
enclosure_body();
translate([width + 25, lid_length, lid_thickness]) 
    rotate([180, 0, 0]) 
    top_lid();
