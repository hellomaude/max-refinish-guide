// mast_socket.scad — holds an 8 mm steel or M8 threaded rod as the light mast.
// Printed plastic is the wrong material for a 300 mm mast carrying a light; a
// metal rod in a printed socket is the right split.
//
// mount = "deck" bolts through the deck, which is the normal case once the
// tank is the base and the deck is the structure. mount = "rim" clamps the
// tank's top trim directly, for a build with no deck.
// Two per light, one at each end. Print as modelled, socket up: the rim slot
// bridges 14 mm and needs no supports.

include <common.scad>

mount     = "deck";                   // "deck" or "rim"
rod_d     = 8;
socket_id = rod_d + 2 * slop;
socket_od = socket_id + 2 * wall;
socket_h  = 60;                       // grip length on the rod
foot_h    = 90;                       // rim mount: wall reaching down the glass
pilot_d   = 3.6;                      // M4 self-tapping set screw into PETG
                                      // (drill to 5.0 for an M4 heat-set insert)
boss_d    = 12;
boss_h    = 6;
sad_len   = socket_od + 4 * wall;
plate_x   = 56;                       // deck mount: base plate, square
plate_t   = 6;
bolt_d    = 4.4;
bolt_in   = 7;

base_top  = (mount == "rim") ? saddle_top : plate_t;
set_z     = base_top + socket_h * 0.6;

module mast_socket() {
    difference() {
        union() {
            if (mount == "rim")
                rim_saddle(len = sad_len, outer_foot = foot_h);
            else
                rounded_plate(plate_x, plate_x, plate_t, 4);
            translate([0, 0, base_top - eps])
                cylinder(d = socket_od, h = socket_h);
            // flare at the base of the socket, clear of the rim slot
            translate([0, 0, base_top - eps])
                cylinder(d1 = socket_od + 2 * wall, d2 = socket_od, h = 2 * wall);
            translate([0, 0, set_z])
                rotate([-90, 0, 0])
                    cylinder(d = boss_d, h = socket_od / 2 + boss_h);
        }
        // rod bore, closed at the bottom: the base is the rod's stop
        translate([0, 0, base_top])
            cylinder(d = socket_id, h = socket_h + 2);
        // set-screw pilot, from the outside face into the bore
        translate([0, 0, set_z])
            rotate([-90, 0, 0])
                cylinder(d = pilot_d, h = socket_od / 2 + boss_h + 2);
        if (mount != "rim")
            corner_holes(plate_x, plate_x, bolt_in, bolt_d, plate_t);
    }
}

mast_socket();
