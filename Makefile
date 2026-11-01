.PHONY: all build reproduce-small test clean

all: build

build:
	./build.sh

reproduce-small: build
	python3 scripts/reproduce_small.py

test: build
	ctest --test-dir build --output-on-failure

clean:
	rm -rf build /tmp/lifelong-* /tmp/reproduce_small
