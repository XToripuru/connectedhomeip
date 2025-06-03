#!/bin/bash
set -e

apt update && apt install -y gdb-multiarch

# For each target
for target in out/*; do
    # For each coredump
    for zip in "$target/dump"/*.zip; do
        basepath=$(dirname "$zip")
        filename=$(basename "$zip")
        binary="${filename%%_*}"
        path="$basepath/${filename%.*}"
        coredump="$path/${filename%.*}.coredump"

        unzip "$zip" -d "$basepath"
        tar -xf "$path"/*.tar -C "$path"

        echo "----------------------------------------------------------------------------------------------------"
        gdb-multiarch --batch -ex "set auto-load safe-basepath /" -ex "set sysroot ${TIZEN_SDK_SYSROOT}" -ex "bt full" "$target/$binary" "$coredump"
    done
done