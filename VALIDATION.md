# Validation

What was tested on real hardware before release, and what was not.
Everything here ran on Xiaomi CR8808 hardware (M79A, IPQ5018 + QCN6122 +
QCA8337, 256 MB RAM, 128 MB NAND), flashed with factory.ubi via the
trigsoft web U-Boot UI, with:

- a wired client on a LAN port (1 GbE), the WAN port on an upstream LAN
  with internet access (300 Mbps line);
- Wi-Fi clients (the user's own phones/laptops) on each band;
- references measured on the same bench: the same line, the same clients.

Base for all builds below: kuncy7/openwrt-nss-edma, branch
`c3po-tag-8021q`, pinned commit `13e8bc91` (2026-10-31), kernel 6.18.55;
kuncy7/nss-packages, branch `ipq50xx-rebase`, pinned commit `4fa071ab`;
NSS firmware 12.5-210-MP, NSS_MEM_PROFILE_LOW.

Each result names the build it ran on. A build is only "verified" when it
ran on the hardware with the feature working; a green CI run is not
on-device verification.

| Build | What it adds / what was checked |
|---|---|
| #35 | NSS fix (QCA8337 port 5 disabled, WAN conduit back on eth1, upstream `a67d696c5d` applied). Verified on device 2026-11-11: 100 Mbps link -> 99 Mbps, CPU flat. NSS baseline. |
| #36 | NSS confirmed on device. WiFi preset did NOT run: wifi-preset lost its exec bit (mode 100644 in commit `6e20bb2f`), so procd never started it. |
| #37 | All new presets lost: pushed to repo-root `etc/...` instead of `files/etc/...`, so the workflow never copied them into the image. Deleted (user order 2026-11-11). |
| #38 | Presets fixed (files moved to `files/etc/`, workflow chmod added). Verified on device: HE80, 320 Mbps on the 300 Mbps line; eth1 MTU 1504 (QCA8337 DSA tag). |
| #39 | CN 160 MHz regdb patch (wireless-regdb 2026.09.03, CN 5150-5350 merged to @ 160). Verified on device 2026-11-11: `iw dev phy1-ap0 info` shows channel 36 (5180 MHz), width 160 MHz, center1 5250 MHz. 2.4G channel 4, 20 MHz. AU channel 100 tested and FAILED (radar in that band in China); reverted. |
| #42 | 5G CN ch36 HE160 + wifi-keep-multicast (restores multicast_to_unicast_all / bss_transition / wnm_sleep_mode after LuCI Save). Dispatched 2026-11-11 (run 43004822937, HEAD 10153091). Build/on-device status unknown — no result reported. |
| #43 | Closing build: multicast fix (`multicast_to_unicast_all`, the correct key) + new firmware names (M79A/M81). CI green for both M79A and M81 (tags `M79A-6.18-12.5-43-1`, `M81-6.18-12.5-43-1`). NOT flashed; whether to flash is the user's decision. |

Kept releases: #35, #38, #41, #42, #43. Deleted (user order 2026-11-11):
#29, #30, #32, #33, #34, #37. #41 is kept but its test results are not
recorded here. Rebuilds start from #42, the version the user is running
and has verified; #35 remains the NSS baseline.

## Changes not yet built or tested (2026-11-14)

The following were pushed to the repo after #43 and verified only by
source review, local `patch --dry-run` against the exact versioned
source, and workflow YAML validation. No build has been triggered for
them; they are untested until the user orders a build and flashes it.

- REO fragment patch 990 (adapted for backports-7.2; `patches/999-999-cr880x-990-ath11k-reo-misc-ctl-ipq5018.patch`).
  Dry-run clean after kuncy7 999-907; hunk #3 dropped (QCN6122 shares
  ipq5018_regs in backports-7.2, no separate regs struct).
- PTK rekey patch 0009 (`patches/0009-wifi-scripts-wpa-deny-ptk0-rekey.patch`).
  Dry-run clean against the pinned wifi-scripts files.
- `files/usr/sbin/nss_diag.sh` (one-click NSS/ECM/GRO diagnostic),
  `files/usr/sbin/cr880x-q6-policy` + `files/etc/init.d/cr880x-q6` +
  `files/etc/hotplug.d/firmware/09-cr880x-q6` (Q6 crash dump policy,
  coredump disabled by default), `files/sbin/cpuusage` (CLI CPU% + NSS
  load + ECM count), `files/etc/init.d/cr880x-smp-affinity` (dual-core
  IRQ affinity, switchable via `/etc/config/smp_affinity`). All
  shell-syntax checked; modes verified via tree API (init.d/sbin 100755).
- wifi-preset: `wnm_sleep_mode_no_keys='1'` and `time_advertisement='2'`
  added (both verified in ap.uc, schema, and LuCI wireless.js), plus an
  idempotency guard (skip if encryption already set on both interfaces).
  wifi-keep-multicast restores the two new options on every boot.
- Workflow anchor checks (regdb 2026.09.03, backports 7.2, kuncy7
  999-907, nss feed ECM 0060, ap.uc append_vars line) — fail fast if
  upstream moves. Workflow fragment check (`configs/combine.sh --check`).
- Config fragments (`configs/fragments/` + `configs/combine.sh` with
  `--preview` / `--check`). `--check` verified locally: fragments
  reproduce both committed device configs' CONFIG sets exactly, no
  duplicate symbols.
- ECM startup order: verified no problem — the pinned nss-packages
  `4fa071ab` qca-nss-ecm.init deliberately has no START, and nothing in
  the build chain starts ECM at boot. No change made.
- ECM 9001 (QoS tags): already in the pinned feed as patch 0060
  (`4fa071ab`). No change made.
- pbuf tuning + NSS slimming: NOT applied. In the pinned tree pbuf.uci
  already has `auto_scale 'on'` (not `'1'`) and `scaling_governor
  'performance'` already commented out, so the wrt_release seds are
  no-ops; and `auto_scale 'on'` is deliberate (the driver only reports
  CPU utilization to cpu_load_ubi while scaling is enabled). None of
  the slimming targets (wifi-meshmgr, vxlanmgr, macsec, etc.) are
  selected in either defconfig or the base tree's target files.
- LuCI CPU% fix: NOT done as a LuCI change. The wrt_release sed pattern
  does not exist in current LuCI master (verified by cloning LuCI);
  LuCI no longer computes CPU% via top in rpcd. The `cpuusage` CLI
  script covers the same numbers.

## Not tested

- M81 hardware: never verified on a real M81 unit (only M79A). The M81
  build is CI-green only.
- A multi-day soak (the longest single runs were hours).
- The Q6 crash dump policy on a real Q6 crash (no crash has been
  observed to trigger it).
- The IRQ affinity script's effect on throughput/latency (no benchmark
  run against it).
- REO patch 990's effect on Wi-Fi throughput or stability (no build
  yet, no on-device run).
- The PTK rekey patch's effect on rekey behaviour (no build yet).
- The two new Wi-Fi preset options on a real client (no build yet).
