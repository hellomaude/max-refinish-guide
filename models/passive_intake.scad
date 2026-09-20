// passive_intake.scad — the make-up air inlet. Louvres are angled so there is
// no straight line of sight through the plate: bugs and light stay out, air
// gets in. A filter pad drops into the pocket on the underside.
// Print flat on the bed; 45 deg louvres are self-supporting.

include <common.scad>

vent_x     = 140;
vent_y     = 70;
frame_w    = 9;
plate_t    = 4;
louver_t   = 2.2;
louver_gap = 8;      // pitch between louvres
louver_a   = 45;     // degrees off horizontal
pocket_z   = 6;      // filter pocket depth on the underside
bolt_d     = 4.4;    // M4 clearance
bolt_inset = 4.5;

open_x   = vent_x - 2 * frame_w;
open_y   = vent_y - 2 * frame_w;
n_louver = floor(open_y / louver_gap);

// Angled slats, trimmed to the opening by the caller.
module louvres() {
    for (i = [0 : n_louver - 1])
        translate([0, -open_y / 2 + louver_gap / 2 + i * louver_gap, plate_t / 2])
            rotate([louver_a, 0, 0])
                cube([open_x, louver_t, louver_gap * 1.9], center = true);
}

module passive_intake() {
    union() {
        difference() {
            union() {
                rounded_plate(vent_x, vent_y, plate_t, 4);
                // filter pocket walls hanging below the plate
                translate([0, 0, -pocket_z])
                    difference() {
                        rounded_plate(open_x + 2 * wall, open_y + 2 * wall, pocket_z, 3);
                        translate([0, 0, -eps])
                            rounded_plate(open_x, open_y, pocket_z + 2 * eps, 2);
                    }
            }
            // the air opening, cut through plate and pocket
            translate([-open_x / 2, -open_y / 2, -pocket_z - eps])
                cube([open_x, open_y, plate_t + pocket_z + 2 * eps]);
            corner_holes(vent_x, vent_y, bolt_inset, bolt_d, plate_t);
        }
        // louvres added back inside the opening only
        intersection() {
            louvres();
            translate([0, 0, plate_t / 2])
                cube([open_x, open_y, plate_t], center = true);
        }
    }
}

passive_intake();
