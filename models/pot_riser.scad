// pot_riser.scad — open grid tile that lifts pots out of the humidity tray so
// roots are never standing in water and air can move under the canopy.
// Tiles butt against each other; print as many as the footprint needs.
// Flat on the bed, no supports.

include <common.scad>

tile   = 120;   // tile is square
cell   = 20;    // open cell pitch
rib    = 2.6;   // rib width
deck_z = 6;     // deck thickness
foot_h = 22;    // clearance under the deck
foot   = 16;    // foot footprint
n_cell = floor((tile - rib) / cell);

module deck() {
    difference() {
        rounded_plate(tile, tile, deck_z, 3);
        for (ix = [0 : n_cell - 1], iy = [0 : n_cell - 1])
            translate([-n_cell * cell / 2 + rib / 2 + ix * cell,
                       -n_cell * cell / 2 + rib / 2 + iy * cell,
                       -eps])
                cube([cell - rib, cell - rib, deck_z + 2 * eps]);
    }
}

module pot_riser() {
    union() {
        translate([0, 0, foot_h]) deck();
        for (dx = [-1, 1], dy = [-1, 1])
            translate([dx * (tile / 2 - foot / 2 - 2),
                       dy * (tile / 2 - foot / 2 - 2), 0])
                difference() {
                    cylinder(d = foot, h = foot_h + eps);
                    translate([0, 0, -eps])
                        cylinder(d = foot - 2 * wall, h = foot_h - wall);
                }
    }
}

pot_riser();
