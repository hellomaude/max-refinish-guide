// probe_clip.scad — holds the controller's temperature/humidity probe at
// canopy height instead of letting it dangle in the warmest air at the lid.
// Saddle grips the tank's top trim; the arm sets the height; the C-clip takes
// the probe body. Print with the saddle opening facing up.

include <common.scad>

drop      = 90;                 // how far below the rim the probe sits
arm_t     = 5;
arm_w     = 14;
clip_id   = probe_d + 2 * slop;
clip_wall = 2.4;
clip_len  = 26;
clip_gap  = probe_d * 0.62;     // mouth width: snaps on, stays on

module c_clip() {
    difference() {
        cylinder(d = clip_id + 2 * clip_wall, h = clip_len);
        translate([0, 0, -eps])
            cylinder(d = clip_id, h = clip_len + 2 * eps);
        // mouth
        translate([0, -clip_gap / 2, -eps])
            cube([clip_id / 2 + clip_wall + eps, clip_gap, clip_len + 2 * eps]);
    }
}

module probe_clip() {
    union() {
        rim_saddle(len = arm_w + 2 * wall);
        // Arm hangs on the INSIDE face and starts outboard of the rim slot, so
        // the saddle can still seat on the trim.
        translate([-arm_w / 2, -(rim_w / 2 + slop + arm_t), -drop])
            cube([arm_w, arm_t, drop + saddle_top]);
        // Mouth faces +x: the probe snaps in from the side, clear of the arm.
        translate([0, -(rim_w / 2 + slop + arm_t + clip_id / 2), -drop])
            c_clip();
    }
}

probe_clip();
