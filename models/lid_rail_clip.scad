// lid_rail_clip.scad — captures the edge of the lid sheet and hooks over the
// tank's top trim, so the lid is held without adhesive, screws or drilled
// glass. Four to six per tank. Set `lift` above zero if you would rather run a
// deliberate perimeter gap than a louvred intake plate.
// Print with the saddle opening facing up.

include <common.scad>

clip_len = 45;
reach    = 26;             // how far the channel reaches over the lid
shelf_t  = 3;              // material under and over the sheet
lift     = 0;              // perimeter air gap above the rim
gap      = lid_t + 0.6;    // sheet slot height

saddle_top = rim_h * 0.8 + wall;
chan_z     = saddle_top + lift;
span_y     = reach + rim_w / 2 + wall;

module lid_rail_clip() {
    union() {
        rim_saddle(len = clip_len);
        if (lift > 0)
            translate([-clip_len / 2, -(rim_w / 2 + wall), saddle_top - eps])
                cube([clip_len, rim_w + 2 * wall, lift + eps]);
        difference() {
            translate([-clip_len / 2, -(rim_w / 2 + wall) - reach, chan_z - eps])
                cube([clip_len, span_y, 2 * shelf_t + gap]);
            // the slot the sheet slides into
            translate([-clip_len / 2 - eps,
                       -(rim_w / 2 + wall) - reach - eps,
                       chan_z + shelf_t])
                cube([clip_len + 2 * eps, reach + eps, gap]);
        }
    }
}

lid_rail_clip();
