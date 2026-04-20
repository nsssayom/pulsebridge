# Convenience wrappers around `docker compose run`.
# Run everything from impl/gem5/docker/:
#   make image           # build the container image
#   make build-gem5      # scons build/ARM_MESI_Two_Level/gem5.opt
#   make build-m5        # scons build/arm64/out/m5 (aarch64 m5ops libm5.a)
#   make build-workload  # cross-compile bench-aarch64-{unsync,seqlock,dblbuf}+stress
#   make smoke           # one-cell smoke test (seqlock on duty_bias)
#   make matrix          # full sweep via scripts/run_matrix.sh
#   make shell           # interactive shell in the container
#   make clean           # drop the image and named volumes

DC := docker compose
RUN := $(DC) run --rm gem5
JOBS ?= 4

.PHONY: image shell build-gem5 build-m5 build-workload smoke matrix \
        clean-workload clean-gem5 clean down

image:
	$(DC) build

shell:
	$(DC) run --rm gem5 bash

build-gem5:
	$(RUN) bash -c '\
	    bash /impl/gem5/docker/gem5-patches/apply-patches.sh && \
	    cd /gem5 && scons build/ARM_MESI_Two_Level/gem5.opt -j$(JOBS)'

build-m5:
	$(RUN) bash -c '\
	    bash /impl/gem5/docker/gem5-patches/apply-patches.sh && \
	    cd /gem5/util/m5 && scons build/arm64/out/m5 -j$(JOBS)'

build-workload:
	$(RUN) bash -c '\
	    bash /impl/gem5/docker/gem5-patches/apply-patches.sh && \
	    make -C /impl/gem5/workload'

smoke:
	$(RUN) bash -c '\
	    mkdir -p /impl/results/gem5/smoke/m5out && \
	    /gem5/build/ARM_MESI_Two_Level/gem5.opt \
	        --outdir=/impl/results/gem5/smoke/m5out \
	        /impl/gem5/configs/two_core_ruby.py \
	        --bench-bin /impl/gem5/workload/build/bench-aarch64-seqlock \
	        --workload-dir /impl/workloads/synthesized/duty_bias \
	        --cpu-type TimingSimpleCPU'

matrix:
	$(RUN) bash /impl/gem5/scripts/run_matrix.sh

clean-workload:
	$(RUN) make -C /impl/gem5/workload clean

clean-gem5:
	$(RUN) bash -c 'cd /gem5 && rm -rf build/'

down:
	$(DC) down

clean: down
	$(DC) down --rmi local --volumes
