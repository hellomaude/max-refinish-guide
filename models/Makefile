# Export every part to STL. Needs OpenSCAD on PATH.
#   make            -> stl/*.stl
#   make stl/duct_collar.stl
#   make clean
SCAD  := $(wildcard *.scad)
PARTS := $(filter-out common.scad,$(SCAD))
STL   := $(PARTS:%.scad=stl/%.stl)

all: $(STL)

stl/%.stl: %.scad common.scad
	@mkdir -p stl
	openscad --export-format binstl -o $@ $<

check: $(PARTS)
	@for f in $(PARTS); do openscad -o /dev/null $$f || exit 1; done
	@echo "all parts compile"

clean:
	rm -rf stl

.PHONY: all check clean
