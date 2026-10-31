PY = .venv/bin/python
CMAKE = .venv/bin/cmake
CONFIG ?= configs/base.yaml
RUN ?= demo
.PHONY: setup data build test research report demo
setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt
data:
	$(PY) -m research.store --synthetic
build:
	$(CMAKE) -S . -B build -DPython3_EXECUTABLE=$(CURDIR)/$(PY)
	$(CMAKE) --build build -j2
test: build
	MPLCONFIGDIR=/tmp/market-signal-mpl $(PY) -m pytest -q
	.venv/bin/ctest --test-dir build --output-on-failure
research: build
	MPLCONFIGDIR=/tmp/market-signal-mpl OMP_NUM_THREADS=1 $(PY) -m research.run --config $(CONFIG) --run-id $(RUN)
report:
	MPLCONFIGDIR=/tmp/market-signal-mpl $(PY) -c "from reporting.report import generate; generate('artifacts/$(RUN)')"
demo: build
	MPLCONFIGDIR=/tmp/market-signal-mpl OMP_NUM_THREADS=1 $(PY) -m research.run --run-id $(RUN)
