// chamber_corner.scad — the grow chamber is four sheets standing on the deck.
// These are its corners: a 90-degree extrusion with a groove down each wing
// that a panel slides into. Stack `spline` segments up the height of the box
// and use `foot` at the bottom, where it screws down to the deck.
//
// There are deliberately no alignment pins between segments: once the panels
// are in their grooves the panels themselves are the alignment, the foot
// carries the stack, and a lid_rail_clip (jaw set to panel_t) caps it.
//
// Print standing up, as modelled. part = "spline" or "foot".

include <common.scad>

part    = "spline";
seg_h   = 100;                    // segment height; stack as many as you need
leg     = 28;                     // how far each wing reaches along a wall
slot_w  = panel_t + 2 * slop;
back    = 3.5;                    // material outboard of the panel
inner   = 3;                      // material inboard of the panel
foot_h  = 35;
base_x  = 52;                     // foot base plate, square
base_t  = 5;
screw_d = 4.4;                    // M4 clearance into the deck

t_total = back + slot_w + inner;

module corner_profile() {
    difference() {
        union() {
            square([leg, t_total]);
            square([t_total, leg]);
        }
        // grooves, open at each wing tip so a panel slides in from the end
        translate([t_total, back])
            square([leg - t_total + eps, slot_w]);
        translate([back, t_total])
            square([slot_w, leg - t_total + eps]);
    }
}

module spline(h = seg_h) {
    linear_extrude(height = h) corner_profile();
}

module foot() {
    difference() {
        union() {
            translate([0, 0, base_t - eps]) spline(h = foot_h);
            translate([base_x / 2 - 4, base_x / 2 - 4, 0])
                rounded_plate(base_x, base_x, base_t, 4);
        }
        // Screws land inboard on the bare plate, clear of both panel grooves
        // (panels occupy y 3.5-7.1 and x 3.5-7.1), so a driver can reach them
        // before the sheets slide in.
        for (pt = [[38, 14], [14, 38]])
            translate([pt[0], pt[1], -eps])
                cylinder(d = screw_d, h = base_t + 2 * eps);
    }
}

if (part == "foot") foot(); else spline();
