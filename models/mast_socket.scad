// mast_socket.scad — rim bracket that holds an 8 mm steel or M8 threaded rod
// as the light mast. Printed plastic is the wrong material for a 300 mm mast
// carrying a light; a metal rod in a printed socket is the right split.
// Two sockets per tank, one at each end. Print with the saddle opening up.

include <common.scad>

rod_d     = 8;                        // 8 mm rod or M8 threaded rod
socket_id = rod_d + 2 * slop;
socket_od = socket_id + 2 * wall;
socket_h  = 60;                       // grip length on the rod
foot_h    = 90;                       // outer wall reaching down the glass
pilot_d   = 3.6;                      // M4 self-tapping set screw into PETG
                                      // (drill to 5.0 for an M4 heat-set insert)
boss_d    = 12;
boss_h    = 6;
sad_len   = socket_od + 4 * wall;
set_z     = saddle_top + socket_h * 0.6;

module mast_socket() {
    difference() {
        union() {
            rim_saddle(len = sad_len, outer_foot = foot_h);
            translate([0, 0, saddle_top - eps])
                cylinder(d = socket_od, h = socket_h);
            // flare where the socket meets the saddle, above the rim slot
            translate([0, 0, saddle_top - eps])
                cylinder(d1 = socket_od + 2 * wall, d2 = socket_od, h = 2 * wall);
            // set-screw boss on the outside face
            translate([0, 0, set_z])
                rotate([-90, 0, 0])
                    cylinder(d = boss_d, h = socket_od / 2 + boss_h);
        }
        // rod bore: closed at the bottom, the saddle's top plate is the stop
        translate([0, 0, saddle_top])
            cylinder(d = socket_id, h = socket_h + 2);
        // set-screw pilot, from the outside face into the bore
        translate([0, 0, set_z])
            rotate([-90, 0, 0])
                cylinder(d = pilot_d, h = socket_od / 2 + boss_h + 2);
    }
}

mast_socket();
