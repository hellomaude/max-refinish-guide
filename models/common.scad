// common.scad — shared parameters for the aquarium grow-box parts.
// Everything downstream is driven from here. Measure YOUR tank, fan and lid
// with calipers and edit this file; do not trust the defaults.

$fn = 96;

/* ---------------- measured inputs ---------------- */
glass_t  = 6;      // tank wall glass thickness. 20-long / 29 gal is usually 5-6 mm.
rim_w    = 14;     // width of the plastic top trim, front to back
rim_h    = 16;     // height of the plastic top trim
lid_t    = 3;      // lid sheet thickness. 3 mm polycarbonate is the default.
duct_nom = 101.6;  // 4 in duct. Use 152.4 for a 6 in fan.
probe_d  = 10;     // sensor-probe body diameter
cable_d  = 6;      // fattest cable that must pass through the lid

/* ---------------- print fit ---------------- */
slop = 0.35;  // clearance per side on sliding fits
wall = 3;     // default wall thickness
eps  = 0.01;  // z-fighting guard

/* ---------------- helpers ---------------- */

// A ring of clearance holes, drilled from z=0 upward.
module bolt_ring(count, radius, hole_d, depth) {
    for (i = [0 : count - 1])
        rotate([0, 0, i * 360 / count])
            translate([radius, 0, -eps])
                cylinder(d = hole_d, h = depth + 2 * eps);
}

// Rounded rectangular plate centred on the origin, sitting on z=0.
module rounded_plate(x, y, z, r = 4) {
    hull()
        for (dx = [-1, 1], dy = [-1, 1])
            translate([dx * (x / 2 - r), dy * (y / 2 - r), 0])
                cylinder(r = r, h = z);
}

// Four corner clearance holes inset from the edges of an x by y plate.
module corner_holes(x, y, inset, hole_d, depth) {
    for (dx = [-1, 1], dy = [-1, 1])
        translate([dx * (x / 2 - inset), dy * (y / 2 - inset), -eps])
            cylinder(d = hole_d, h = depth + 2 * eps);
}

// Upside-down U that straddles the tank's top trim. Opening faces -z, length
// runs along x. -y is the tank interior, +y is the outside.
// `outer_foot` extends the outer wall down the outside glass: that is what
// stops a hanging load from levering the part off the rim. Put a strip of EVA
// foam between the foot and the glass.
// Print with the opening facing up, no supports.
module rim_saddle(len = 40, jaw = rim_w, depth = rim_h * 0.8, t = wall,
                  outer_foot = 0) {
    union() {
        difference() {
            translate([-len / 2, -(jaw / 2 + t), 0])
                cube([len, jaw + 2 * t, depth + t]);
            translate([-len / 2 - eps, -(jaw / 2 + slop), -eps])
                cube([len + 2 * eps, jaw + 2 * slop, depth + eps]);
        }
        if (outer_foot > 0)
            translate([-len / 2, jaw / 2 + slop, -outer_foot])
                cube([len, t - slop, outer_foot + eps]);
    }
}

// Height of the top face of a default rim_saddle.
saddle_top = rim_h * 0.8 + wall;

// Right-triangle brace: base `len` along +x, `height` along +z, `thick` in -y.
module gusset(len, height, thick) {
    rotate([90, 0, 0])
        linear_extrude(height = thick)
            polygon([[0, 0], [len, 0], [0, height]]);
}
