# Device block for Xiaomi CR8808 (M81), A版. The base tree has no M81
# profile, so the workflow appends this file to
# target/linux/qualcommax/image/ipq50xx.mk at build time (see
# "Install custom devices"). It mirrors the xiaomi_cr8806 block, with:
# - no ALT entries (CR8808 M79 stays an ALT of cr8806; this is M81 only)
# - no ipq-wifi package: M81 board data comes from the per-device files
#   overlay (files-xiaomi_cr8808/), because no ipq-wifi-xiaomi_cr8808
#   package exists. The workflow fails fast if those board files are
#   missing, so a build never silently ships with wrong Wi-Fi data.
# - same FIT config (config@mp02.1), NAND geometry and radios as M79;
#   hzyitc covers M79 and M81 with a single DTS, which is the evidence
#   they match, but LED/button GPIOs and the NAND layout are NOT yet
#   verified on M81 hardware in this tree.
# When the base tree gains a real M81 profile, delete this file and the
# matching .dts and point the config at the base profile.

define Device/xiaomi_cr8808
	$(call Device/FitImage)
	$(call Device/UbiFit)
	DEVICE_VENDOR := Xiaomi
	DEVICE_MODEL := CR8808
	DEVICE_VARIANT := M81
	DEVICE_DTS_CONFIG := config@mp02.1
	SOC := ipq5018
	BLOCKSIZE := 128k
	PAGESIZE := 2048
	NAND_SIZE := 128m
	DEVICE_PACKAGES := \
		ath11k-firmware-ipq5018-qcn6122
endef
TARGET_DEVICES += xiaomi_cr8808
