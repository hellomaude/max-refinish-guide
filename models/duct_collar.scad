// duct_collar.scad — bolts through the lid and gives the flexible duct a
// spigot to clamp onto. This is the only exhaust penetration in the build.
// Print upright, spigot up. No supports needed.

include <common.scad>

spigot_od = duct_nom - 0.8;        // slides INSIDE the flex duct
spigot_id = spigot_od - 2 * wall;
flange_od = spigot_od + 28;
flange_t  = 4;
spigot_h  = 38;
bead_z    = 26;                    // retaining bead height above the flange
bead_d    = 3;                     // bead cross-section
bolts     = 6;
bolt_d    = 4.4;                   // M4 clearance
gasket_w  = 5;                     // width of the silicone-bead groove
gasket_z  = 1.2;                   // depth of that groove

module duct_collar() {
    difference() {
        union() {
            cylinder(d = flange_od, h = flange_t);
            translate([0, 0, flange_t - eps])
                cylinder(d = spigot_od, h = spigot_h);
            translate([0, 0, flange_t + bead_z])
                rotate_extrude()
                    translate([spigot_od / 2, 0])
                        circle(d = bead_d);
        }
        // through bore
        translate([0, 0, -eps])
            cylinder(d = spigot_id, h = flange_t + spigot_h + 2);
        // lid bolts
        bolt_ring(bolts, (flange_od - 11) / 2, bolt_d, flange_t);
        // sealant groove on the underside: lay a silicone bead in here so the
        // printed layer lines never have to be the humidity seal
        translate([0, 0, -eps])
            difference() {
                cylinder(d = spigot_id + 6 + 2 * gasket_w, h = gasket_z + eps);
                translate([0, 0, -eps])
                    cylinder(d = spigot_id + 6, h = gasket_z + 3 * eps);
            }
    }
}

duct_collar();
