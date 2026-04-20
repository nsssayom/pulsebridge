CC      ?= cc
AR      ?= ar
CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -Wpedantic -Wno-unused-parameter
CFLAGS  += -Iinclude

BUILD   ?= build

COMMON_OBJS := $(BUILD)/residual.o $(BUILD)/stl_policy.o

PROTOCOLS := unsync seqlock dblbuf

LIBS := $(foreach p,$(PROTOCOLS),$(BUILD)/libcore-$(p).a)

.PHONY: all clean
all: $(LIBS)

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

define PROTOCOL_LIB
$(BUILD)/libcore-$(1).a: $(BUILD)/publish_$(1).o $(COMMON_OBJS)
	$(AR) rcs $$@ $$^
endef

$(foreach p,$(PROTOCOLS),$(eval $(call PROTOCOL_LIB,$(p))))

clean:
	rm -rf $(BUILD)
