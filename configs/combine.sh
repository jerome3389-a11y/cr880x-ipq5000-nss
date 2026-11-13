#!/bin/sh
# Combine .config fragments into a device .config (CR880x).
#
# The device configs in configs/ are assembled from fragments in
# configs/fragments/ so a feature change (NSS, SQM, LuCI, adblock) is
# edited once instead of being mirrored across two near-identical files.
# Combination order (later fragments cannot override an earlier CONFIG
# line — defconfig takes the last value, so keep each symbol in exactly
# one fragment):
#   00-device-<dev>.config  device header + device selection line
#   10-target.config        shared target (qualcommax/ipq50xx)
#   20-nss.config           NSS plane (firmware, memory profile, drv, wifili)
#   30-system.config        initramfs, LuCI, ZRAM, BBR, ccache, Argon, tools, -O3
#   40-network.config       NSS SQM, luci-app-nss, dnsmasq, adblock
#   50-removed.config       deliberately NOT configured (documentation only)
#
# Usage:
#   combine.sh cr8806            print combined config to stdout
#   combine.sh cr8806 out.config write combined config to out.config
#   combine.sh --preview cr8806  print order + combined config (no write)
#   combine.sh --check           verify fragments reproduce the committed
#                                configs/cr8806-256m.config and
#                                configs/cr8808-m81-256m.config (CONFIG
#                                lines must match exactly; comments may differ)
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
FRAG="$DIR/fragments"

usage() {
	echo "usage: combine.sh [--preview] <cr8806|cr8808> [out.config]" >&2
	echo "       combine.sh --check" >&2
	exit 1
}

combine() {
	_dev="$1"
	case "$_dev" in
		cr8806) _devfile="00-device-cr8806.config" ;;
		cr8808) _devfile="00-device-cr8808.config" ;;
		*) echo "unknown device: $_dev (want cr8806 or cr8808)" >&2; exit 1 ;;
	esac
	for _f in "$_devfile" 10-target.config 20-nss.config 30-system.config 40-network.config 50-removed.config; do
		[ -f "$FRAG/$_f" ] || { echo "missing fragment: $_f" >&2; exit 1; }
		cat "$FRAG/$_f"
	done
}

check_one() {
	_dev="$1"
	_committed="$2"
	_tmp=$(mktemp)
	_tmp2=$(mktemp)
	_tmp3=$(mktemp)
	combine "$_dev" > "$_tmp"
	# CONFIG order in the file does not matter to `make defconfig`
	# (flat key=value list; the device line sits first here but third
	# in the committed file), so compare sorted. Duplicates ARE an
	# error: defconfig silently takes the last value, so a symbol in
	# two fragments would hide a conflict.
	_dups=$(grep '^CONFIG' "$_tmp" | sed 's/=.*//' | sort | uniq -d)
	if [ -n "$_dups" ]; then
		echo "CHECK FAILED: duplicate CONFIG symbol(s) in $_dev fragments:" >&2
		echo "$_dups" >&2
		rm -f "$_tmp" "$_tmp2" "$_tmp3"
		return 1
	fi
	grep '^CONFIG' "$_tmp" | sort > "$_tmp2"
	grep '^CONFIG' "$_committed" | sort > "$_tmp3"
	if ! diff "$_tmp2" "$_tmp3" > /dev/null; then
		echo "CHECK FAILED: fragments do not reproduce $_committed" >&2
		diff "$_tmp2" "$_tmp3" >&2 || true
		rm -f "$_tmp" "$_tmp2" "$_tmp3"
		return 1
	fi
	rm -f "$_tmp" "$_tmp2" "$_tmp3"
	echo "CHECK OK: $_dev fragments reproduce $_committed"
}

if [ "${1:-}" = "--check" ]; then
	_fail=0
	check_one cr8806 "$DIR/cr8806-256m.config" || _fail=1
	check_one cr8808 "$DIR/cr8808-m81-256m.config" || _fail=1
	[ "$_fail" = "0" ] || exit 1
	exit 0
fi

if [ "${1:-}" = "--preview" ]; then
	shift
	_dev="${1:-}"; [ -n "$_dev" ] || usage
	echo "=== combination order for $_dev ==="
	echo "  00-device-$_dev.config"
	echo "  10-target.config"
	echo "  20-nss.config"
	echo "  30-system.config"
	echo "  40-network.config"
	echo "  50-removed.config"
	echo "=== combined config (preview, not written) ==="
	combine "$_dev"
	exit 0
fi

_dev="${1:-}"; [ -n "$_dev" ] || usage
if [ -n "${2:-}" ]; then
	combine "$_dev" > "$2"
else
	combine "$_dev"
fi
