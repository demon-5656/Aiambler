CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -pedantic -Os
LDFLAGS ?= -s -pthread

BUILD_DIR := build
NATIVE_BIN := $(BUILD_DIR)/aiambler

.PHONY: all native test-native clean

all: native

native: $(NATIVE_BIN)

$(NATIVE_BIN): native/aiambler.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $< -o $@ $(LDFLAGS)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

test-native: native
	tests/native_smoke.sh $(NATIVE_BIN)

clean:
	rm -rf $(BUILD_DIR)
