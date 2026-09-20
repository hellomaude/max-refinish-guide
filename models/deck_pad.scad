// deck_pad.scad — the load path. The chamber sits on a deck; the deck sits on
// these; these sit on the tank's top trim. Their whole job is to turn a few
// point loads into a long, even line load along the rim, and to stop the deck
// sliding without fastening anything to the tank.
// Six to eight per tank, evenly spaced along the two long sides.
// Print as modelled, pegs up: the rim slot bridges and needs no supports.

include <common.scad>

pad_len  = 90;                    // long on purpose — this is the spreader
pad_t    = 5;                     // bearing plate over the rim
pad_w    = rim_w + 2 * wall;      // flush with the saddle, no overhang to print
peg_d    = 8;                     // locating peg into the deck's underside
peg_h    = 10;
peg_gap  = 46;                    // peg spacing
foam_t   = 1.5;                   // relief for the EVA strip on the rim

module deck_pad() {
    difference() {
        union() {
            rim_saddle(len = pad_len);
            translate([0, 0, saddle_top - eps])
                rounded_plate(pad_len, pad_w, pad_t, 3);
            for (dx = [-1, 1])
                translate([dx * peg_gap / 2, 0, saddle_top + pad_t - eps])
                    cylinder(d1 = peg_d, d2 = peg_d - 1.4, h = peg_h);
        }
        // shallow relief so the EVA foam strip has somewhere to live and the
        // print's first layer never bears directly on glass
        translate([0, 0, rim_h * 0.8 - eps])
            translate([-pad_len / 2 + 4, -(rim_w / 2 - 2), 0])
                cube([pad_len - 8, rim_w - 4, foam_t]);
    }
}

deck_pad();
