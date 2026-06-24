CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -pedantic -Os
LDFLAGS ?= -s -pthread

BUILD_DIR := build
NATIVE_BIN := $(BUILD_DIR)/aiambler

.PHONY: all native test-native bench-agent bench-tokens clean

all: native

native: $(NATIVE_BIN)

$(NATIVE_BIN): native/aiambler.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

test-native: native
	tests/native_smoke.sh $(NATIVE_BIN)

bench-agent: native
	python3 benchmarks/agent_tasks.py --runs 20

bench-tokens:
	python3 benchmarks/token_count.py

clean:
	rm -rf $(BUILD_DIR)
