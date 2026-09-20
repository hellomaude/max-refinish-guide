# Printed parts — aquarium grow box

Parametric OpenSCAD sources for the parts that turn a standard glass aquarium
into a climate-controlled grow box. Nothing here is decorative: each part exists
because the alternative is drilling the tank, gluing something to it, or letting
a cable hole leak humidity into the room.

## 1. Measure first

Every model reads its numbers from `common.scad`. Measure your own tank, lid and
probe with calipers and edit that file before you slice anything.

| Variable | What it is | Default |
|---|---|---|
| `glass_t` | tank wall glass thickness | 6 mm |
| `rim_w` | width of the plastic top trim, front to back | 14 mm |
| `rim_h` | height of the plastic top trim | 16 mm |
| `lid_t` | lid sheet thickness | 3 mm |
| `duct_nom` | duct size: 101.6 (4 in) or 152.4 (6 in) | 101.6 mm |
| `probe_d` | controller sensor probe diameter | 10 mm |
| `cable_d` | fattest cable passing through the lid | 6 mm |

`slop` (0.35 mm per side) is the clearance on sliding fits. If your printer runs
tight, raise it before you scale anything.

## 2. Parts

| File | Qty | Job | Print orientation |
|---|---|---|
| `lid_rail_clip.scad` | 4–6 | Holds the lid sheet and hooks over the trim. No glue, no drilled glass. Set `lift` above 0 for a deliberate perimeter gap instead of a louvred intake. | On its side, length flat on the bed |
| `duct_collar.scad` | 1 | Bolts through the lid; gives the flex duct a spigot and clamp bead. The only exhaust penetration. | Upright, spigot up |
| `passive_intake.scad` | 1 | Make-up air inlet. 45° louvres block line of sight, so light and bugs stay out. Filter pad drops into the pocket. | Flat; louvres are self-supporting |
| `fan_port.scad` | 0–1 | Mounts an 80 mm or 120 mm axial fan (MULTIFAN S1/S3) to the lid with a filter pocket. Use instead of the duct collar on small tanks. | Flat, pocket up |
| `cable_grommet.scad` | 1–2 | Two-piece pass-through with a side slot, so you never cut a plug off a cable. Cap pinches a silicone collar around the bundle. | Both halves flat |
| `probe_clip.scad` | 1 | Puts the temperature/humidity probe at canopy height instead of in the hot air under the lid. | On its side, flat back down |
| `mast_socket.scad` | 2 | Rim bracket holding an 8 mm steel or M8 rod as the light mast. The extended foot down the outside glass is what stops the load levering it off the rim. | As modelled, socket up; the rim slot bridges |
| `mast_hook.scad` | 2 | Split collar that pinches the mast at any height and reaches inboard to carry a light hanger cord. Loosen, slide, retighten — that is your light-height adjustment. | Collar axis vertical |
| `pot_riser.scad` | 2–6 | Open grid tile lifting pots out of the humidity tray. Tiles butt together. | Flat |

A 300 mm printed mast carrying a light is a creep failure waiting to happen,
which is why the mast is a metal rod and only the brackets are printed.

## 3. Material and print settings

Print in **PETG** (or ASA). Not PLA: its glass transition is around 55–60 °C, and
a part that sits under a grow light in a warm, humid lid will sag and creep. PETG
is around 80 °C and shrugs off the humidity. Nylon absorbs water and moves.

| Setting | Value | Why |
|---|---|---|
| Nozzle / layer | 0.4 mm / 0.2 mm | — |
| Walls | 4 (≈1.6 mm) | Humidity resistance is wall count, not infill |
| Top / bottom | 5 layers | Same |
| Infill | 30–40 % gyroid | Brackets carry a real load |
| Supports | none | Every part is oriented to avoid them |
| Brim | on `mast_socket`, `probe_clip` | Tall and narrow |

**FDM prints are not watertight.** Do not ask the layer lines to be the seal.
Lay a bead of 100 % RTV silicone (aquarium-grade, no mildewcide or
"antimicrobial" additive — those are what kill livestock) in the groove on the
duct collar and under every plate that bolts to the lid.

Keep printed parts out of direct contact with the LED board's heat sink.

## 4. Hardware

- M4 × 16 bolts, washers and nylock nuts — collar, vent, fan port (about 16)
- M3 × 20 bolt and nut — grommet cap, mast hook pinch (2 each)
- 8 mm steel rod or M8 threaded rod, ~450 mm, two off — light masts
- M4 × 10 self-tapping screws, two off — mast set screws (or M4 heat-set inserts;
  drill the pilot to 5.0 mm for those)
- EVA foam tape — between every printed foot and the glass
- Cut-to-size filter pad — intake pocket
- 100 % RTV aquarium silicone — sealing beads

## 5. Export

```sh
make          # every part to stl/
make check    # compile-only pass over every part
make clean
```

Both targets need `openscad` on your PATH. The grommet builds both halves at
once by default; export them separately with `-D`:

```sh
openscad -D 'part="base"' -o stl/grommet_base.stl cable_grommet.scad
openscad -D 'part="cap"'  -o stl/grommet_cap.stl  cable_grommet.scad
```

A deck-mounted variant of `mast_socket` — for a build where something stands on
the tank rather than growing in it — is in this repo's history at commit
`2eeebec`, along with the deck pad and chamber-corner parts that went with it.

**Verification status:** these sources were written and reviewed by hand;
OpenSCAD could not be installed in the environment they were authored in, so
they have not been compiled or test-printed. Run `make check` first, then open
each STL in your slicer and eyeball it against the dimensions above before you
commit filament to it.
