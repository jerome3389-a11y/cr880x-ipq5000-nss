# 加设备：CR8808 / CR8809 / m79 A/B / m81

本仓库目前只有 CR8806 的基线。加新设备时按下面顺序做，不要跳步，
尤其不要把 CR8806 的镜像改个名就当成别板子的固件发出去。

> 前提：本仓库只放脚本和配置，设备 profile/DTS 在底包
> （kuncy7/openwrt-nss-edma）里。加设备 = 先在底包侧把 profile
> 做出来（fork 底包或给底包提 PR），再回本仓库加配置和矩阵。

## 第 0 步：先把硬件定义清楚（不做这步，后面全是猜）

m79 / m81 是主板版本，不是型号；CR880x 的细分见 README 的
CR880x 硬件细分表（A版/B版 × M79/M81）：A版 M81（CTR66266）
与 A版 M79（MXD7223，无 PA）共用 QCA8337，B版 M79（CR881x）
是 IPQ5018 + YT9215S，固件与 A版不通用。动手之前，对每一台
样机记录：

1. 主板丝印：M79 还是 M81，有没有 A/B 后缀（拆机或从散热孔
   打光看，主板名印在左上角）。
2. FEM（射频前端）型号：M79 和 M81 的区别就在 FEM 上，选错
   镜像的直接后果就是射频异常（历史上 M79 出现过 2.4 GHz
   功率减半）。
3. ART/caldata：从设备自己的 ART 分区 dump 一份存档。
   **不要把别的板子的 caldata 拷进新板子的镜像。**
4. 原厂固件版本和闪存布局：确认是不是 128 MB NAND 双 slot。
   CR8808/CR8809 的闪存布局目前只是按家族推测，**未按型号确认**，
   必须实测，不能直接套 CR8806 的。
5. 如果 A 和 B 的 FEM/caldata 确实不同，就按两个 profile 做；
   如果查完发现 A/B 只是同一块板子的不同叫法，把证据写下来，
   再合并成一个 profile。不要在没证据的情况下发一个“m79 通用”镜像。

## 第 1 步：在底包侧做 profile

按底包 README《Porting to another IPQ5018 board》一节：

1. DTS 里加一行 `#include "ipq5018-nss.dtsi"`。没有这一行，
   `nss@40000000` 节点不存在，`qca-nss-drv` 永远不会 probe，
   而且是静默失败——能开机、能 ping、LAN 互通都正常，
   只是没有任何流量进 NSS。
2. 核对 GMAC / phys_if 对应关系：phys_if N 就是 GMAC N。
   CR880x 这类带 QCA8337 的板子，交换机一般挂在一个 GMAC 上，
   另一个 GMAC 可能空着或接独立 WAN PHY。
3. DSA 拓扑（默认）不需要 `nss-dwmac.defaults` 表项：交换机
   保持 DSA 驱动，布线在每次启动时从板子读出来。只有当板子
   的交换机做不了 `qca-8021q` tagger、必须走 trunk 拓扑时，
   才需要写 VTU / switch_args（`nss.general.vtu`、
   `nss.general.switch_args`，以及 `bus_via` / `wake_phys`，
   从 `ls /sys/bus/mdio_bus/devices/` 和 DTS 的
   `ethernet-switch` 节点里读出来）。
4. LED、按键、闪存分区按实测写进 DTS，不要从 CR8806 复制
   后不验证。

## 第 2 步：回本仓库加配置

1. 复制 `configs/cr8806-256m.config` 为新文件（例如
   `configs/cr8808-m79-256m.config`），只改设备符号那一行，
   例如：
   `CONFIG_TARGET_qualcommax_ipq50xx_DEVICE_xiaomi_cr8808=y`
   （符号名以底包里实际的 profile 名为准）。
2. 所有 CR880x 都是 256 MB，必须保留 `CONFIG_NSS_MEM_PROFILE_LOW=y`
   和 256M 的 ath11k 配置；不要因为“就加几个包”放宽内存。
3. 每个包加之前先算内存账：CR8806 上 Linux 可见约 169 MiB，
   空闲时只剩 20–30 MiB。

## 第 3 步：往 workflow 矩阵里加一行

两处要改（都在 `.github/workflows/build-ipq50xx.yml` 里）：

1. `workflow_dispatch` 的 `device` 选项里加新 profile 名。
2. `strategy.matrix.device` 列表里加新 profile 名（注释里有例子）。
3. “Apply device config”那一步的 `case` 里加一行映射，
   例如：
   `xiaomi_cr8808) CONFIG_FILE="cr8808-m79-256m.config" ;;`

## 第 4 步：上机冒烟测试（每块板子、每次首发都跑）

先按 CR8806 的首次安装方式走一遍（UART + TFTP + initramfs，
之后 sysupgrade），但**先按自己板子实测的 slot 布局来**，
不要照搬 CR8806 的步骤。启动后依次确认：

```sh
ls /etc/rc.d | grep S19nss
# 应该有 nss 服务

logread -e nss
# 最后应该出现 "NSS wired plane + ECM up"

cat /sys/kernel/debug/qca-dwmac-nss/status
# 端口应该显示 started

# 跑 iperf 流量时：
cat /sys/kernel/debug/ecm/ecm_nss_ipv4/tcp_accelerated_count
# 应该 > 0

grep -m1 ipv4_rx_pkts /sys/kernel/debug/qca-nss-drv/stats/ipv4
# 应该持续上涨

nft list flowtables
# 应该什么都不输出（有输出说明 flow offloading 还开着）

top
# 满速流量下 idle 应该保持在 90% 以上
```

还要逐项测：双频 Wi-Fi（2.4 GHz + 5 GHz 都上 NSS 路径）、
PPPoE（含带 VLAN 的情况，如 `wan.35`）、802.1Q VLAN、
VLAN-aware 桥、LED/按键、多客户端。
以下在 IPQ5018 上属于“代码里有、未实测”，测完之前不要写进
发布说明：IPv6 路由、组播、MAP-T/DS-Lite、802.11s mesh
（mesh 只在 std 组验证过，256m 组未验证）。

## 第 5 步：发布时附带的东西

每次发布（workflow 目前只传 artifacts，将来开 release 时也一样）
都要带上：sysupgrade 镜像、initramfs 镜像（如果有）、
`config.buildinfo`、`feeds.buildinfo`、`sha256sums.txt`。
这是 GPL 源码提供义务的一部分，也是以后复现某次编译的唯一依据。
发布说明里写清楚：哪些测过、哪些没测、首次安装方式、
NSS 固件是专有二进制 blob（不是开源）。
