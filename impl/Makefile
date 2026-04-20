.PHONY: all core prototype workloads gem5-workload \
        docker-image docker-shell docker-build-gem5 docker-build-m5 \
        docker-build-workload docker-smoke docker-matrix docker-clean \
        clean help

all: core

core:
	$(MAKE) -C core

prototype: core
	$(MAKE) -C prototype

workloads:
	$(MAKE) -C workloads

gem5-workload:
	$(MAKE) -C gem5/workload

# Docker-based gem5 workflow — delegates to gem5/docker/Makefile so
# the top-level entry points mirror what the README documents.
docker-image:
	$(MAKE) -C gem5/docker image
docker-shell:
	$(MAKE) -C gem5/docker shell
docker-build-gem5:
	$(MAKE) -C gem5/docker build-gem5
docker-build-m5:
	$(MAKE) -C gem5/docker build-m5
docker-build-workload:
	$(MAKE) -C gem5/docker build-workload
docker-smoke:
	$(MAKE) -C gem5/docker smoke
docker-matrix:
	$(MAKE) -C gem5/docker matrix
docker-clean:
	$(MAKE) -C gem5/docker clean

clean:
	-$(MAKE) -C core clean
	-$(MAKE) -C prototype clean
	-$(MAKE) -C workloads clean
	-$(MAKE) -C gem5/workload clean

help:
	@echo "Targets:"
	@echo "  core                  build C11 core library (three libcore-*.a)"
	@echo "  prototype             build host harness (requires core)"
	@echo "  workloads             regenerate synthesized workload CSVs"
	@echo "  gem5-workload         cross-compile gem5 SE benchmark (aarch64)"
	@echo "  clean                 clean all subtrees"
	@echo ""
	@echo "Docker (see gem5/docker/.env.example):"
	@echo "  docker-image          build the gem5 container image"
	@echo "  docker-build-gem5     scons build/ARM_MESI_Two_Level/gem5.opt inside the container"
	@echo "  docker-build-m5       scons util/m5/build/arm64/out/m5 (libm5.a for aarch64)"
	@echo "  docker-build-workload cross-compile the SE workload inside the container"
	@echo "  docker-smoke          one-cell smoke test (seqlock on duty_bias)"
	@echo "  docker-matrix         full sweep via scripts/run_matrix.sh"
	@echo "  docker-shell          interactive shell in the container"
	@echo "  docker-clean          remove the image and named docker volumes"
