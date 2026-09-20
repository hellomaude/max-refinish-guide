// cable_grommet.scad — two-piece pass-through for the light cord, the probe
// lead and the clip-fan cable. The side slot means you never have to cut a
// plug off to thread it. The cap squeezes a silicone bead or foam collar
// around the bundle so the hole is not a humidity leak.
// Print both parts flat. part = "base", "cap" or "both".

include <common.scad>

part       = "both";
hole_d     = 25;                    // hole you drill/cut in the LID, not the glass
flange_d   = 46;
flange_t   = 4;
throat_d   = hole_d - 2 * slop;
throat_h   = lid_t + 3;
bore_d     = 16;                    // cable bundle bore
slot_w     = cable_d + 1.5;         // side slot: lay the cable in from outside
screw_d    = 3.4;                   // M3 clearance
screw_r    = (flange_d - 9) / 2;
cap_t      = 5;

module slot(h) {
    translate([0, 0, -eps])
        linear_extrude(height = h + 2 * eps)
            polygon([[0, -slot_w / 2], [flange_d, -slot_w / 2],
                     [flange_d, slot_w / 2], [0, slot_w / 2]]);
}

module grommet_base() {
    difference() {
        union() {
            cylinder(d = flange_d, h = flange_t);
            translate([0, 0, flange_t - eps])
                cylinder(d = throat_d, h = throat_h);
        }
        translate([0, 0, -eps])
            cylinder(d = bore_d, h = flange_t + throat_h + 2);
        slot(flange_t + throat_h);
        for (a = [90, 270])
            rotate([0, 0, a])
                translate([screw_r, 0, -eps])
                    cylinder(d = screw_d, h = flange_t + 2 * eps);
    }
}

module grommet_cap() {
    difference() {
        cylinder(d = flange_d, h = cap_t);
        // tapered throat: pushes the silicone collar inward as it is tightened
        translate([0, 0, -eps])
            cylinder(d1 = bore_d + 4, d2 = bore_d - 2, h = cap_t + 2 * eps);
        slot(cap_t);
        for (a = [90, 270])
            rotate([0, 0, a])
                translate([screw_r, 0, -eps])
                    cylinder(d = screw_d, h = cap_t + 2 * eps);
    }
}

if (part == "base" || part == "both") grommet_base();
if (part == "cap"  || part == "both") translate([flange_d + 10, 0, 0]) grommet_cap();
