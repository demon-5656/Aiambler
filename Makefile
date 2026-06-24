CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -pedantic -Os
LDFLAGS ?= -s -pthread

BUILD_DIR := build
NATIVE_BIN := $(BUILD_DIR)/aiambler

.PHONY: all native test test-native bench-agent bench-multistep bench-tokens clean

all: native

native: $(NATIVE_BIN)

$(NATIVE_BIN): native/aiambler.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

test-native: native
	tests/native_smoke.sh $(NATIVE_BIN)

test: test-native

bench-agent: native
	python3 benchmarks/agent_tasks.py --runs 20

bench-multistep: native
	python3 benchmarks/multistep_tasks.py --runs 20

bench-tokens:
	python3 benchmarks/token_count.py

clean:
	rm -rf $(BUILD_DIR) .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf aiambler.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find benchmarks -maxdepth 1 \( -name 'generated_*.ai' -o -name prices.txt \) -delete
	rm -rf benchmarks/agent_data
	rm -rf benchmarks/multistep_data
