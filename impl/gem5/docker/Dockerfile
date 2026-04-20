# gem5 build environment for the coherent-witness-export project.
#
# Base: ubuntu:22.04 (multi-arch; pulls linux/arm64 on an M-series Mac,
# linux/amd64 on Intel/AMD — either is fine since gem5 always simulates
# the guest ISA, not the host).
#
# Contents:
#   - gem5 build dependencies (scons, protobuf, hdf5, boost, python-dev)
#   - aarch64 Linux glibc cross-compiler (for the SE-mode workload)
#   - a handful of convenience utilities
#
# Entry point is bash so you can `docker compose run --rm gem5` and land
# in a shell with GEM5_ROOT and the cross-compiler already on PATH.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        g++-aarch64-linux-gnu \
        gcc-aarch64-linux-gnu \
        git \
        libboost-all-dev \
        libelf-dev \
        libgoogle-perftools-dev \
        libhdf5-serial-dev \
        libpng-dev \
        libprotobuf-dev \
        libprotoc-dev \
        libzstd-dev \
        m4 \
        pkg-config \
        protobuf-compiler \
        python-is-python3 \
        python3 \
        python3-dev \
        python3-pydot \
        scons \
        zlib1g \
        zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

ENV GEM5_ROOT=/gem5 \
    CC=aarch64-linux-gnu-gcc \
    AR=aarch64-linux-gnu-ar \
    M5_DIR=/gem5/util/m5/build/arm64

WORKDIR /impl/gem5
CMD ["bash"]
