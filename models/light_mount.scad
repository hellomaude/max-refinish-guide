// light_mount.scad — carries the LED board under the lid with an air gap, so
// the box is self-contained and there is no mast hanging off it. Two brackets,
// one at each end of the board. The board tilts in from below and the lip stops
// it dropping back out.
//
// In an all-in-one there is nowhere to dump the light's heat, so the board's
// wattage IS the box's thermostat. Size it to the box, not to a grow tent.
// Print as modelled: the profile lies flat on the bed, no supports.

include <common.scad>

board_t  = 11;      // IONBOARD S22 is 0.43 in; measure yours
ledge    = 10;      // how much board edge sits on the shelf
lip_h    = 5;       // retaining lip
lip_w    = 3;
shelf_t  = 4;
gap      = 14;      // air gap between lid and the top of the board
web_t    = 6;       // drop leg thickness
plate_x  = 40;      // bolt plate reach, outboard of the board
plate_t  = 5;
bw       = 40;      // bracket width
bolt_d   = 4.4;     // M4 clearance

H = shelf_t + board_t + gap + plate_t;   // shelf underside to lid face

module bracket_profile() {
    polygon([
        [0, 0],
        [web_t + ledge + lip_w, 0],
        [web_t + ledge + lip_w, shelf_t + lip_h],
        [web_t + ledge, shelf_t + lip_h],
        [web_t + ledge, shelf_t],
        [web_t, shelf_t],
        [web_t, H],
        [-plate_x, H],
        [-plate_x, H - plate_t],
        [0, H - plate_t]
    ]);
}

module light_mount() {
    difference() {
        linear_extrude(height = bw) bracket_profile();
        // lid bolts, through the plate
        for (zz = [bw * 0.28, bw * 0.72])
            translate([-plate_x * 0.55, H + 1, zz])
                rotate([90, 0, 0])
                    cylinder(d = bolt_d, h = plate_t + 2);
    }
}

light_mount();
