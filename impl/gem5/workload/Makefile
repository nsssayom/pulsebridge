#
# Cross-compile the prototype harness for aarch64 gem5 SE mode.
#
# Requires:
#   - an aarch64 C cross-compiler, e.g. `aarch64-linux-gnu-gcc` on Linux or
#     `/opt/homebrew/bin/aarch64-elf-gcc` on macOS.
#   - the gem5 m5ops library built for aarch64, per gem5 docs
#     (util/m5/build/arm64/out/libm5.a).
#
# Point at them via CC and M5_DIR:
#   make CC=aarch64-linux-gnu-gcc M5_DIR=/path/to/gem5/util/m5/build/arm64
#
# Outputs in build/:
#   bench-aarch64-{unsync,seqlock,dblbuf,dma_naive,dma_seqlock} — five
#       static ELFs, one per publication protocol, that gem5 can load in
#       SE mode. Note the two DMA variants: `dma_naive` skips the
#       publication handshake (torn reads expected); `dma_seqlock` wraps
#       the same DMA engine in a versioned handshake (the fair baseline).
#       A flush-only `cachemaint` variant used to live here but was
#       dropped when gem5 Ruby was found to no-op cache maintenance ops
#       (RubyPort.cc:278: "Cache maintenance operations are not
#       supported in Ruby.").
#   stress-aarch64 — cache-thrash stressor for the contention study.
#
# Sources: the prototype's producer/monitor/torn_detector/workload/main
# compiled unchanged. m5_hooks.h becomes active when GEM5_M5OPS is defined.
#

CC        ?= aarch64-linux-gnu-gcc
AR        ?= aarch64-linux-gnu-ar
M5_DIR    ?= $(GEM5_ROOT)/util/m5/build/arm64
GEM5_INC  ?= $(GEM5_ROOT)/include

CFLAGS    := -std=c11 -O2 -static -Wall -Wextra -Wpedantic -Wno-unused-parameter
CFLAGS    += -pthread
CFLAGS    += -DGEM5_M5OPS=1
# Headers live in two places depending on gem5 version: gem5/include/gem5/*
# is the canonical path (m5ops.h, asm/generic/*), and util/m5/include/*
# survives as a legacy path. Include both so the build works against any
# recent gem5 checkout.
CFLAGS    += -I$(GEM5_INC)
CFLAGS    += -I$(M5_DIR)/../../include
CFLAGS    += -I../../prototype/include
CFLAGS    += -I../../core/include

LDFLAGS   := -L$(M5_DIR)/out -lm5 -pthread

PROTO_SRC := ../../prototype/src
CORE_SRC  := ../../core/src

BUILD     := build

PROTOCOLS := unsync seqlock dblbuf dma_naive dma_seqlock

COMMON_OBJS := \
    $(BUILD)/main.o \
    $(BUILD)/producer.o \
    $(BUILD)/monitor.o \
    $(BUILD)/torn_detector.o \
    $(BUILD)/workload.o \
    $(BUILD)/residual.o \
    $(BUILD)/stl_policy.o

BINS   := $(foreach p,$(PROTOCOLS),$(BUILD)/bench-aarch64-$(p))
STRESS := $(BUILD)/stress-aarch64

.PHONY: all clean check-toolchain

all: check-toolchain $(BINS) $(STRESS)

check-toolchain:
	@command -v $(CC) >/dev/null 2>&1 || { \
	  echo "error: aarch64 cross-compiler '$(CC)' not found."; \
	  echo "       set CC=<your-aarch64-gcc> or install aarch64-linux-gnu-gcc."; \
	  exit 1; }
	@test -f $(M5_DIR)/out/libm5.a || { \
	  echo "error: gem5 m5ops lib not found at $(M5_DIR)/out/libm5.a"; \
	  echo "       build it via: cd \$$GEM5_ROOT/util/m5 && scons build/arm64/out/m5"; \
	  echo "       or set M5_DIR=/path/to/gem5/util/m5/build/arm64"; \
	  exit 1; }

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/main.o:          $(PROTO_SRC)/main.c          | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/producer.o:      $(PROTO_SRC)/producer.c      | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/monitor.o:       $(PROTO_SRC)/monitor.c       | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/torn_detector.o: $(PROTO_SRC)/torn_detector.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/workload.o:      $(PROTO_SRC)/workload.c      | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/residual.o:      $(CORE_SRC)/residual.c       | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/stl_policy.o:    $(CORE_SRC)/stl_policy.c     | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

define PROTO_BIN
$(BUILD)/publish_$(1).o: $(CORE_SRC)/publish_$(1).c | $(BUILD)
	$$(CC) $$(CFLAGS) -c $$< -o $$@
$(BUILD)/bench-aarch64-$(1): $(COMMON_OBJS) $(BUILD)/publish_$(1).o
	$$(CC) $$(CFLAGS) $$^ $$(LDFLAGS) -o $$@
endef

$(foreach p,$(PROTOCOLS),$(eval $(call PROTO_BIN,$(p))))

$(BUILD)/stress.o: stress.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(STRESS): $(BUILD)/stress.o
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

clean:
	rm -rf $(BUILD)
