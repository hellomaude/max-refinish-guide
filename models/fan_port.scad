// fan_port.scad — mounts an 80 mm or 120 mm axial fan (MULTIFAN S1 / S3) to
// the lid and holds a cut-to-size filter pad in a pocket under the blades.
// Set fan_size to 80 or 120. Print flat, pocket up.

include <common.scad>

fan_size   = 120;                                 // 80 or 120
fan_pitch  = (fan_size == 120) ? 105   : 71.5;    // screw hole spacing
fan_bore   = (fan_size == 120) ? 113   : 76;      // free air opening
fan_screw  = 4.4;                                 // M4 clearance
plate_x    = fan_size + 20;
plate_t    = 5;
pocket_z   = 6;                                   // filter pad thickness
lid_bolt   = 4.4;
lid_inset  = 6;

module fan_port() {
    difference() {
        union() {
            rounded_plate(plate_x, plate_x, plate_t, 5);
            // raised rim that forms the filter pocket
            translate([0, 0, plate_t - eps])
                difference() {
                    rounded_plate(fan_size + 8, fan_size + 8, pocket_z, 4);
                    translate([0, 0, -eps])
                        rounded_plate(fan_size + 2, fan_size + 2, pocket_z + 2 * eps, 3);
                }
        }
        // air opening
        translate([0, 0, -eps])
            cylinder(d = fan_bore, h = plate_t + pocket_z + 2);
        // fan screws
        for (dx = [-1, 1], dy = [-1, 1])
            translate([dx * fan_pitch / 2, dy * fan_pitch / 2, -eps])
                cylinder(d = fan_screw, h = plate_t + pocket_z + 2);
        // lid bolts
        corner_holes(plate_x, plate_x, lid_inset, lid_bolt, plate_t);
    }
}

fan_port();
