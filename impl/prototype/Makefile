CC      ?= cc
CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -Wpedantic -Wno-unused-parameter -pthread
CFLAGS  += -Iinclude -I../core/include

BUILD       := build
CORE_BUILD  := ../core/build

PROTOCOLS := unsync seqlock dblbuf

COMMON_SRC := src/main.c src/producer.c src/monitor.c src/torn_detector.c src/workload.c
COMMON_OBJS := $(patsubst src/%.c,$(BUILD)/%.o,$(COMMON_SRC))

BINS := $(foreach p,$(PROTOCOLS),$(BUILD)/harness-$(p))

.PHONY: all clean core

all: core $(BINS)

core:
	$(MAKE) -C ../core

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

define HARNESS_BIN
$(BUILD)/harness-$(1): $(COMMON_OBJS) $(CORE_BUILD)/libcore-$(1).a
	$(CC) $(CFLAGS) $(COMMON_OBJS) $(CORE_BUILD)/libcore-$(1).a -o $$@
endef

$(foreach p,$(PROTOCOLS),$(eval $(call HARNESS_BIN,$(p))))

clean:
	rm -rf $(BUILD)
