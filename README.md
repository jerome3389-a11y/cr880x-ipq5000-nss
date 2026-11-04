# CR880X IPQ5000 NSS

小米 CR880X（CR8806 / CR8808 / CR8809）IPQ5000 平台的 OpenWrt 固件自动编译项目：GitHub Actions 自动编译带 Qualcomm NSS 硬件加速的固件，目标是**最新内核 + 最强 NSS 加速**。本仓库只放编译脚本、配置和设备定义，不放底包源码；编译时 workflow 按钉住的提交克隆底包再编译。

## 基础版本

- OpenWrt SNAPSHOT，底包 [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma)，分支 `c3po-tag-8021q`，钉住提交 `13e8bc914709c4794b3ec7b0421d2038386e697e`
- 内核 **6.18**（6.18.55）
- NSS 固件 **12.5**（12.5-210-MP；编译时可选 12.2，驱动必须与固件版本对应）
- 目标 `qualcommax/ipq50xx`，DSA 拓扑
- Feeds 钉住：packages `24f7c066`、luci `ae19cdfd`、routing `ea8633da`、telephony `9bcb6d71`、video `4582d70f`、nss `4fa071ab`
- LuCI（Argon 为默认主题，Bootstrap 也在镜像里）

## NSS

- 全平面 NSS：qca-nss-drv + qca-nss-ecm、NSS 固件加载、dwmac NSS、ath11k NSS（wifili）、DSA NSS、QCA8337、PPPoE、VLAN、IPv6、虚拟接口
- NSS 内存档：LOW（默认）
- 已在 CR8808（A版 M79）上机验证：NSS 核心启动、有线平面转发零丢包、ECM 已加速 TCP 流、WiFi 测速时 CPU 几乎不变（双频 WiFi 走 NSS 路径）
- 内核 flow offloading（flowtable）必须保持关闭：NSS ECM 是 offload 路径，两者不能同时开
- SQM：sqm-scripts-nss（nssfq_codel）+ luci-app-sqm + ifb，默认关闭
- 交换机桥 IGMP snooping 默认关闭
- bridge-mgr 不在 ipq50xx 上（仅 ipq807x/ipq60xx 的 PPE 栈有），未包含

## 固件特性

- 无线：IPQ5018（2.4G）+ QCN6122（5G），ath11k，双频 WiFi 6（802.11ax）；双频广播已在 CR8808（A版 M79）上机验证
- 出厂默认：双频 radio 全开、SSID 分开（2.4G `OpenWrt` / 5G `OpenWrt_5G`）、802.11k + 802.11v 默认开、802.11r + 802.11s 默认关（LuCI 里可手动开）；完整版 wpad-mbedtls（与 basic 同为 mbedtls 后端，另含 WNM 与 MESH）；WPA3-SAE 可用
- 出厂为开放网络：刷机后请立即在 LuCI 里设 WiFi 密码；root 密码同样需在刷机后设置（LuCI 密码页用户名默认 root，只需填新密码 + 确认 + 保存；或 SSH `passwd`）
- DNS：dnsmasq-full + adblock（默认开启，规则源 anti_ad / adguard / yoyo / disconnect，列表首次开机联网后下载）；LAN 53 端口 DNS 劫持到路由器本机；dnsmasq 缓存 1000；无 SmartDNS
- 网络：DSA（lan / wan）、BBR（首次开机设为默认拥塞算法）、zram（lz4，LZO 备用）、内核 flow offloading 关、IGMP snooping 关、SQM 关
- 工具：htop、zoneinfo-asia、luci-app-upnp、tcpdump-mini、iw（无线调试）、ca-bundle
- 不包含：SmartDNS、ttyd、SFTP/SCP、bridge-mgr、Fullcone、cpufreq、arpbind（feed 里没有或已确认不适用；要加功能请重编译，见下）
- 设备适配：merged 分区 fixed-partitions（单 rootfs 116.5 MiB）、trigsoft 链 4-bit NAND ECC、ART caldata（`0:ART`，脚本按大小写精确匹配）
- 编译优化：`-O3` + Cortex-A53 crypto 指令集、LTO 开启
- 内存：256 MiB 物理内存，Linux 可见约 170 MiB；大规则源（adblock XL/XXL/VAR）默认关闭，别贪大

## 支持的型号

| 固件（profile） | 支持的设备 | 状态 |
|---|---|---|
| `xiaomi_cr8806` | CR8806 / CR8808 / CR8809（A版 M79，共用同一 profile） | 已在 CR8808（A版 M79）上机验证 |
| `xiaomi_cr8808` | CR8808（A版 M81） | 可编译，未上机验证 |
| — | CR881x（B版，IPQ5018 + YT9215S）及其他所有型号 | 不支持，刷错变砖 |

认板看主板版号 + 板型，不要只看型号：CR8808 有 M79 和 M81 两种主板；A版与 B版交换芯片不同，固件不通用。

## 刷机与首次开机

- 当前设备（trigsoft 合并分区，单 rootfs）：按住 reset 通电进 trigsoft web UI（192.168.10.1），刷 `factory.ubi`。`factory.ubi` 是 OpenWrt UBI 镜像，不是原厂格式，不要当原厂固件刷到别的分区。
- sysupgrade 不可用：本设备无平台升级脚本；升级请用 trigsoft web UI 重刷 `factory.ubi`（会清空配置）。
- 首次安装（原厂分区布局）：UART（115200 8N1）+ TFTP，启动 initramfs，把 `factory.ubi` 写到固件 UBI 分区；刷前备份原厂固件。
- 刷坏恢复：断电，按住 reset 再通电，多试几次进 trigsoft web UI，刷回已知好的固件。
- 首次开机：立即设 root 密码 + WiFi 密码（出厂 radio 全开且开放网络）。

## 编译

- `.github/workflows/build-ipq50xx.yml`（瘦调用方）+ `build-ipq50xx-shared.yml`（共用构建），手动触发（`workflow_dispatch`）
- 输入：`device`（`xiaomi_cr8806` / `xiaomi_cr8808`）、`firmware`（`12.5` 默认 / `12.2`）、`base_ref`（底包提交，默认钉住值）
- 每次成功编译发一个独立 Release（tag `设备-日期-运行号-尝试号`）：先发 draft，验远端摘要通过后再发布，坏版永不公开；release 里只有固件（`factory.ubi`）；buildinfo、完整 `.config`、校验文件与第三方来源清单只作 workflow 诊断产物，不进 release
- 缓存：ccache 按工具链 + 编译器键入，staging / dl 按配置哈希键入；旧缓存与旧工作流自动清理（工作流保留 2 天，Release 不受影响）
- 要加功能请重编译：本项目不提供自建 kmod 仓库；kmod 包带内核 vermagic，只能装在同一编译的内核上

## 给 fork 者的建议与注意事项

建议：

- fork 后先钉住自己的 `base_ref` 与 feeds，不要跟分支走，否则无法复现
- 保留 defconfig 守卫、targetinfo DEVICE_PACKAGES 校验、无线校验、factory 结构校验：它们专防配置符号被 defconfig 静默丢掉
- 保留 draft → 验摘要 → 发布：不要直接发布未验的镜像
- 加设备先看 [docs/adding-devices.md](docs/adding-devices.md)：先把硬件定义清楚（丝印、FEM、caldata），再做 profile / DTS，回来复制配置、往 workflow 加映射，最后上机跑冒烟测试

注意事项（硬约束）：

- `nss-tools-dwmac` 必须 `=y`，不能 `=m`，否则 NSS 静默不工作且无任何报错
- 内核 flow offloading 必须关，否则 ECM 看不到流量
- 驱动必须与固件版本对应（12.5 驱动配 12.2 固件，或反过来，WiFi 计数器会一直是 0）
- ART 分区名大小写敏感：caldata 脚本按 `/proc/mtd` 精确匹配，`0:ART` 与 `0:art` 写错一个字母就没 WiFi；移植前先看自己板子的 `/proc/mtd`
- trigsoft 链 NAND ECC 用 4-bit；8-bit 会导致 trigsoft 写过的页无法解码（UBI 挂不上）
- 分区布局：合并分区用 fixed-partitions（smem-part 在 trigsoft 合并表上会失败）；原厂布局用 smem-part；两者不要混用
- M79 的 2.4G 没有 PA（MXD7223 只有 LNA + 收发切换）：2.4G 弱是硬件，改配置修不好；M81（CTR66266）才有正常 2.4G
- B版（YT9215S）在 NSS 树里没有 Linux 驱动，不要把 A版固件往 B版上刷
- NSS 固件是专有二进制 blob，不是开源软件；不要把它说成开源，也不要把它直接塞进仓库（编译时由 feed 链路获取）
- 各设备的 caldata 来自设备自己的 ART 分区，不要拷别的板子的 caldata
- 这是 SNAPSHOT，不是稳定版：底包与 feeds 已钉住以保证复现，rebase 时请重新钉住并验证

## 合规

- 发布镜像时一并附带当次编译的 `config.buildinfo` 与 `feeds.buildinfo`（workflow 已收集），这是 GPL 源码提供义务的一部分
- NSS 固件是专有二进制 blob，不是开源软件；caldata 来自设备自己的 ART 分区
