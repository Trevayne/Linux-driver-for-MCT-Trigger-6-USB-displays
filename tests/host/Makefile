# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2026 Gareth Palmer
#
# Host-side unit tests for the hardware-independent parts of the driver.
#
#   make            build and run all tests (ASan + UBSan)
#   make bench      encoder throughput at -O2 without sanitizers
#
# PYTHON must have Pillow and numpy (used as an independent JPEG decoder).

CC      ?= gcc
PYTHON  ?= python3
OUT     ?= build
CFLAGS  ?= -O1 -g
CFLAGS  += -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function \
           -Wno-sign-compare -I../../src
SANITIZE = -fsanitize=address,undefined -fno-sanitize-recover=all \
           -fno-omit-frame-pointer

TESTS = test_jpeg test_proto

.PHONY: all check bench clean
all: check

$(OUT):
	mkdir -p $@

$(OUT)/test_jpeg: test_jpeg.c ../../src/t6_jpeg.c ../../src/t6_jpeg.h ../../src/t6_types.h | $(OUT)
	$(CC) $(CFLAGS) $(SANITIZE) -o $@ $<

$(OUT)/test_proto: test_proto.c ../../src/t6_proto.c ../../src/t6_proto.h ../../src/t6_types.h | $(OUT)
	$(CC) $(CFLAGS) $(SANITIZE) -o $@ $<

$(OUT)/bench_jpeg: test_jpeg.c ../../src/t6_jpeg.c ../../src/t6_jpeg.h | $(OUT)
	$(CC) -O2 -std=gnu11 -I../../src -o $@ $<

check: $(addprefix $(OUT)/,$(TESTS))
	$(OUT)/test_proto
	rm -rf $(OUT)/jpeg && mkdir -p $(OUT)/jpeg
	$(OUT)/test_jpeg $(OUT)/jpeg
	$(PYTHON) check_jpeg.py $(OUT)/jpeg

bench: $(OUT)/bench_jpeg
	$(OUT)/bench_jpeg --bench

clean:
	rm -rf $(OUT)
