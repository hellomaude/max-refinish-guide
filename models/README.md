# Printed parts — aquarium-based grow box

Parametric OpenSCAD sources for a grow box that stands **on** a glass aquarium.
The tank is the base: dry, structural, carrying ballast and the cable run. A
deck caps it, the grow chamber sits on the deck, and the light rides a rod mast
above that. Nothing here is decorative: each part exists because the
alternative is drilling the tank, gluing something to it, or point-loading a
rim that was never designed to carry anything.

```
            light on an 8 mm rod mast
    ┌──────────────────────────────┐
    │   chamber: 4 sheets + lid    │  ← chamber_corner, lid_rail_clip, ports
    ├──────────────────────────────┤  ← deck: the structure and the moisture boundary
    │   tank: dry, ballast, cables │  ← deck_pad spreads the load onto the rim
    └──────────────────────────────┘
```

## 1. Measure first

Every model reads its numbers from `common.scad`. Measure your own tank, sheets
and probe with calipers and edit that file before you slice anything.

| Variable | What it is | Default |
|---|---|---|
| `glass_t` | tank wall glass thickness | 6 mm |
| `rim_w` | width of the plastic top trim, front to back | 14 mm |
| `rim_h` | height of the plastic top trim | 16 mm |
| `deck_t` | deck sheet: the tank's cap and the chamber's floor | 18 mm |
| `panel_t` | chamber wall sheet thickness | 3 mm |
| `lid_t` | chamber lid sheet thickness | 3 mm |
| `duct_nom` | duct size: 101.6 (4 in) or 152.4 (6 in) | 101.6 mm |
| `probe_d` | controller sensor probe diameter | 10 mm |
| `cable_d` | fattest cable passing through the chamber | 6 mm |

`slop` (0.35 mm per side) is the clearance on sliding fits. If your printer runs
tight, raise it before you scale anything.

## 2. Parts

| File | Qty | Job | Print orientation |
|---|---|---|---|
| `deck_pad.scad` | 6–8 | **The load path.** Straddles the rim, turns the chamber's weight into an even line load, and locates the deck on two pegs without fastening anything to the tank. | As modelled, pegs up; the rim slot bridges 14 mm |
| `chamber_corner.scad` | 8–16 | Corner extrusion with a groove down each wing; the chamber walls slide in. `part="foot"` screws to the deck, `part="spline"` stacks above it. | Standing up, as modelled |
| `lid_rail_clip.scad` | 4–6 | Holds the chamber lid on the wall tops. Set `jaw = panel_t` for the chamber (the default suits the tank rim). | Saddle opening up |
| `duct_collar.scad` | 1 | Bolts through the chamber lid; gives the flex duct a spigot and clamp bead. | Upright, spigot up |
| `passive_intake.scad` | 1 | Make-up air inlet. 45° louvres block line of sight, so light and bugs stay out. Filter pad drops into the pocket. | Flat, louvres self-supporting |
| `fan_port.scad` | 0–1 | Mounts an 80 mm or 120 mm axial fan with a filter pocket. Use instead of the duct collar on a small chamber. | Flat, pocket up |
| `cable_grommet.scad` | 1–2 | Two-piece pass-through with a side slot, so you never cut a plug off a cable. | Both parts flat |
| `probe_clip.scad` | 1 | Puts the temperature/humidity probe at canopy height. Set `jaw = panel_t` to clip a chamber wall instead of a rim. | On its side, flat back down |
| `mast_socket.scad` | 2 | Holds the 8 mm rod mast. `mount="deck"` bolts through the deck (normal); `mount="rim"` clamps the tank trim for a deckless build. | As modelled, socket up |
| `mast_hook.scad` | 2 | Split collar that pinches the mast at any height and reaches in to carry a light hanger cord. | Collar axis vertical |
| `pot_riser.scad` | 2–6 | Open grid tile lifting pots out of the humidity tray. Tiles butt together. | Flat |

A 300 mm printed mast carrying a light is a creep failure waiting to happen,
which is why the mast is a metal rod and only the brackets are printed.

## 3. The load path, in one paragraph

An aquarium's plastic top trim is a brace that stops the glass bowing — it is
not a beam, and it is not a shelf. It will carry a chamber quite happily as an
**even line load along the glass edges**, and quite badly as four point loads in
the middle of a span. That is the entire reason `deck_pad` is 90 mm long and
why you want six to eight of them rather than four corner blocks. Foam between
every printed face and the glass, and the deck rigid enough not to sag between
pads (18 mm ply, not 6 mm).

## 4. Material and print settings

Print in **PETG** (or ASA). Not PLA: its glass transition is around 55–60 °C, and
a part that sits under a grow light in a warm, humid chamber will sag and creep.
PETG is around 80 °C and shrugs off the humidity. Nylon absorbs water and moves.

| Setting | Value | Why |
|---|---|---|
| Nozzle / layer | 0.4 mm / 0.2 mm | — |
| Walls | 4 (≈1.6 mm) | Humidity resistance is wall count, not infill |
| Top / bottom | 5 layers | Same |
| Infill | 30–40 % gyroid | Deck pads and corners carry a real load |
| Supports | none | Every part is oriented to avoid them |
| Brim | `mast_socket`, `chamber_corner` | Tall and narrow |

**FDM prints are not watertight.** Do not ask the layer lines to be the seal.
Lay a bead of 100 % RTV silicone (aquarium-grade, no mildewcide or
"antimicrobial" additive — those are what kill livestock) in the groove on the
duct collar and under every plate that bolts through the chamber lid.

Keep printed parts out of direct contact with the LED board's heat sink.

## 5. Hardware

- M4 × 16 bolts, washers and nylock nuts — collar, vent, fan port, mast plates (about 24)
- M4 × 30 screws — chamber feet into the deck (2 per foot)
- M3 × 20 bolt and nut — grommet cap, mast hook pinch (2 each)
- 8 mm steel rod or M8 threaded rod, ~450 mm, two off — light masts
- M4 × 10 self-tapping screws, two off — mast set screws (or M4 heat-set
  inserts; drill the pilot to 5.0 mm for those)
- EVA foam tape — between every printed foot and the glass
- Cut-to-size filter pad — intake pocket
- 100 % RTV aquarium silicone — sealing beads

## 6. Export

```sh
make          # every part to stl/
make check    # compile-only pass over every part
make clean
```

Both targets need `openscad` on your PATH. For the parts with a `part` or
`mount` variable, export each variant with `-D`:

```sh
openscad -D 'part="foot"'   -o stl/chamber_corner_foot.stl chamber_corner.scad
openscad -D 'mount="rim"'   -o stl/mast_socket_rim.stl     mast_socket.scad
```

**Verification status:** these sources were written and reviewed by hand;
OpenSCAD could not be installed in the environment they were authored in, so
they have not been compiled or test-printed. Run `make check` first, then open
each STL in your slicer and eyeball it against the dimensions above before you
commit filament to it.
