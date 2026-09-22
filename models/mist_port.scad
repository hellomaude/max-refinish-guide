// mist_port.scad — where the humidifier's hose enters. The humidifier itself
// stays outside on the bench: its tank needs refilling, its electronics must
// not live in a wet box, and it is the one part you want to reach without
// opening anything.
//
// Two details that matter more than the geometry:
//   - Mount the hose so it slopes DOWN into the box. Condensate then drains
//     into the box instead of running back into the humidifier.
//   - The mouth is cut at 45 degrees so mist is thrown along the glass, never
//     straight down onto the leaves. The bolt ring is at 90-degree spacing:
//     rotate the whole part to aim it.
//
// Print upright, spigot up; the 45-degree mouth is self-supporting.

include <common.scad>

hose_id   = 22;                 // MEASURE your humidifier's hose
spigot_od = hose_id - 0.5;      // slides inside the hose
port_wall = 2;
bore      = spigot_od - 2 * port_wall;
spigot_h  = 26;
barb_d    = 2.4;
barb_z    = 16;
flange_od = spigot_od + 34;
flange_t  = 4;
drop      = 30;                 // how far the tube reaches into the box
bolts     = 4;
bolt_d    = 4.4;

module mist_port() {
    difference() {
        union() {
            cylinder(d = flange_od, h = flange_t);
            translate([0, 0, flange_t - eps])
                cylinder(d = spigot_od, h = spigot_h);
            // barb ridge: the hose clamp seats behind this
            translate([0, 0, flange_t + barb_z])
                rotate_extrude()
                    translate([spigot_od / 2, 0])
                        circle(d = barb_d);
            // tube reaching down into the box
            translate([0, 0, -drop])
                cylinder(d = spigot_od, h = drop + eps);
        }
        translate([0, 0, -drop - 1])
            cylinder(d = bore, h = drop + flange_t + spigot_h + 2);
        bolt_ring(bolts, (flange_od - 11) / 2, bolt_d, flange_t);
        // 45-degree mouth on the inside end. The cut is clipped to the lower
        // end of the drop tube so the rotated half-space cannot reach up and
        // take a bite out of the flange.
        intersection() {
            translate([0, 0, -drop])
                rotate([-45, 0, 0])
                    translate([-50, -100, -100])
                        cube([100, 100, 100]);
            translate([-spigot_od, -spigot_od, -drop - 1])
                cube([2 * spigot_od, 2 * spigot_od, spigot_od + 1]);
        }
    }
}

mist_port();
