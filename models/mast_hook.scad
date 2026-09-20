// mast_hook.scad — split collar that pinches the 8 mm mast at any height and
// reaches inboard to carry one of the light's hanger cords. Two per light.
// Loosen the M3 bolt, slide, retighten: that is the light-height adjustment.
// Print collar-axis vertical, arm flat on the bed.

include <common.scad>

rod_d     = 8;
collar_id = rod_d + 2 * slop;
collar_od = collar_id + 2 * wall;
collar_h  = 22;
slit_w    = 2;
ear_x     = 7;      // ear thickness either side of the slit
ear_y     = 15;     // how far the ears reach past the collar
bolt_d    = 3.4;    // M3 clearance
arm_len   = 60;     // reach in over the tank
arm_w     = 12;
arm_t     = 7;
hook_d    = 8;      // cord / carabiner hole
hook_gap  = 4.5;    // open throat so a cord drops in

module ears() {
    for (sx = [-1, 1])
        translate([sx * (slit_w / 2 + ear_x / 2), collar_od / 2 + ear_y / 2 - 1, collar_h / 2])
            cube([ear_x, ear_y, collar_h * 0.7], center = true);
}

module arm() {
    translate([-arm_w / 2, -(collar_od / 2 + arm_len), collar_h / 2 - arm_t / 2])
        cube([arm_w, arm_len + collar_od / 2, arm_t]);
}

module mast_hook() {
    difference() {
        union() {
            cylinder(d = collar_od, h = collar_h);
            ears();
            arm();
        }
        // rod bore
        translate([0, 0, -eps])
            cylinder(d = collar_id, h = collar_h + 2 * eps);
        // pinch slit, from the bore out through the ears
        translate([-slit_w / 2, 0, -eps])
            cube([slit_w, collar_od / 2 + ear_y + 2, collar_h + 2 * eps]);
        // pinch bolt across the ears
        translate([-(slit_w / 2 + ear_x + 2), collar_od / 2 + ear_y * 0.55, collar_h / 2])
            rotate([0, 90, 0])
                cylinder(d = bolt_d, h = slit_w + 2 * ear_x + 4);
        // cord hole with an open throat at the end of the arm
        translate([0, -(collar_od / 2 + arm_len - hook_d), collar_h / 2 - arm_t / 2 - eps]) {
            cylinder(d = hook_d, h = arm_t + 2 * eps);
            translate([-hook_gap / 2, -hook_d, 0])
                cube([hook_gap, hook_d, arm_t + 2 * eps]);
        }
    }
}

mast_hook();
