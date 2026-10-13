PY ?= .venv/bin/python

.PHONY: test figures check preview

test:
	$(PY) -m pytest -q

figures:
	@set -e; for build in header/build.py figures/*/build.py; do \
		if [ -f "$$build" ]; then $(PY) "$$build"; fi; \
	done

check:
	$(PY) tools/check_svgs.py

preview:
	PY="$(PY)" tools/preview.sh
