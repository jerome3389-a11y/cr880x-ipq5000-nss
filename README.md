# ipq50xx-openwrt-nss

IPQ50xx 设备的 OpenWrt 固件自动编译项目：用 GitHub Actions 自动编译带
Qualcomm NSS 硬件加速的固件，目标是**最新内核 + 最强 NSS 加速**。

> 本仓库只放编译脚本和配置，不放底包源码。编译时 workflow 会从底包仓库
> 克隆指定提交的代码再编译。2026-11-03 第 5 次编译已成功（全部特性），
> Release 已发布；上机实测（NAT/IPv6/WiFi/SQM/dnsmasq 缓存）仍待做。
> Fullcone、cpufreq、arpbind 已确认不在钉住的 feed 里，已从配置里去掉。

## 固件特点

- **NSS 硬件加速（全平面）**：ECM、NSS 驱动、PPPoE、VLAN 管理、
  DSA NSS、dwmac NSS、QCA8337 NSS、Wi-Fi offload、
  ath11k NSS，QCN6122 固件，256 MB 板子用 LOW 内存档，
  NSS 固件默认 **12.5-210-MP**（备选 12.2-156-MP.R）。
  注意：bridge-mgr 不在 ipq50xx 上（qca-nss-clients 把它限定在
  ipq807x/ipq60xx 的 PPE 栈，EDMA 树没有它），不要把它写进配置。
- **编译优化**：`-O3` + Cortex-A53 crypto 指令集优化
 （`march=armv8-a+crypto+crc`，用户已验证可通过云编译）；
  不开 LTO（已知容易把编译机内存撑爆）。
- **TCP BBR**：BBR 模块 + 首次开机 sysctl 设为默认拥塞算法
  （内核配置里的默认值写法会被 defconfig 丢掉，见配置注释）。
- **ZRAM**：zram-swap + LZ4 压缩（LZO 做备用），256 MB 板子
  拿少量 CPU 换可用内存，缓解 OOM。
- **NSS SQM 硬件队列**：sqm-scripts-nss（nssfq_codel，走
  conduit eth0，不走 DSA 口 wan）+ luci-app-sqm + ifb；
  默认关闭，在 LuCI 里启用并按实际带宽填写。
- **dnsmasq 缓存 + DNS 劫持**：dnsmasq（底包默认解析器，
  首次开机把缓存从默认 150 条调到 1000 条）；首次开机
  自动加一条重定向规则，所有 LAN 的 53 端口流量都转到
  路由器本机，客户端写死的 8.8.8.8 也绕不过去。
- **Argon 主题**：luci-theme-argon + luci-app-argon-config，
  编译时从上游拉最新 master（底包 feed 里没有）；首次开机
  自动设为 LuCI 默认主题（Bootstrap 也在镜像里，可随时换回）。
- **小工具**：htop、zoneinfo-asia、upnp。
- **LuCI 保留**；initramfs 镜像保留，用于 UART + TFTP
  首次安装。
- **编译缓存**：工作流缓存 `openwrt/.ccache`，每次运行
  存新缓存、前缀匹配恢复上一次；超 10 GB 由 GitHub 按
  最久未用自动淘汰，另有删旧缓存步骤。
- **自动发布**：每次成功编译发一个独立 Release，tag 是
  `设备-日期-运行号-尝试号`；附带 sysupgrade 镜像、
  factory 镜像、initramfs 镜像（如果有）、
  `config.buildinfo`、`feeds.buildinfo`、`sha256sums.txt`。
- **自动清理**：删旧缓存、删旧工作流（保留 2 天），
  两步都设为失败不影响任务，清理失败不会导致发布失败；
  Release 文件和运行记录分开存，清理不动 Release。
- **首次开机脚本**：仓库 `files/` 目录会打进镜像，
  `files/etc/uci-defaults/99-custom` 在首次开机时设置
  BBR 默认、DNS 劫持规则并调大 dnsmasq 缓存，跑完自动删除。

默认说明：内核 flow offloading（flowtable）必须关（底包
首次启动会清掉它，否则 ECM 会被饿死）；交换机桥上的
IGMP snooping 默认关；SQM 默认关。

### NSS 加速功能表

NSS 固件 12.5-210-MP，LOW 内存档。“包含”指编进了镜像，实机测试前
一律标未测试，实测后逐项改；不包含的直接写不支持。

| 功能 | 状态 | 说明 |
|---|---|---|
| ECM 核心加速 | 未测试 | NSS 连接管理器，NAT/路由流量的核心 offload 引擎 |
| PPPoE 加速 | 未测试 | PPPoE 拨号流量的 offload |
| VLAN 加速 | 未测试 | VLAN 流量的 offload |
| DSA 交换加速 | 未测试 | DSA 拓扑下交换端口的 offload |
| 以太网 MAC 加速 | 未测试 | 以太网口的 offload（dwmac） |
| QCA8337 交换芯片加速 | 未测试 | 本板交换芯片的 offload |
| RTL8367S 交换芯片加速 | 未测试 | 编进了镜像，但本板交换芯片是 QCA8337，板上是否起作用待实测 |
| WiFi 加速 | 未测试 | 双频 WiFi 流量的 offload（wifili，ath11k NSS，QCN6122） |
| IPv6 加速 | 未测试 | NSS IPv6 流量的 offload |
| 虚拟接口加速 | 未测试 | NSS 虚拟接口支持 |
| NSS 硬件队列 | 未测试 | SQM 走 NSS 硬件队列（nssfq_codel，conduit eth0） |
| 桥接加速 | 不支持 | bridge-mgr 仅 ipq807x/ipq60xx 的 PPE 栈有，ipq50xx EDMA 树没有此模块 |

注：内核 flow offloading 必须保持关闭（否则 ECM 看不到流量），它不属于
NSS 加速；Fullcone NAT 也不属于 NSS，且钉住的 feed 里没有对应包，未包含。

### 无线功能表

本板无线：IPQ5018 + QCN6122，ath11k 驱动，双频 WiFi 6。支持指硬件/驱动
能力，不代表默认开启；待确认项需实测或核对驱动后改。

| 功能 | 状态 | 说明 |
|---|---|---|
| WiFi 6（802.11ax） | 支持 | 双频 11ax |
| 2.4GHz 40MHz 频宽 | 支持 | 拥挤环境可能因共存机制回落 20MHz |
| 5GHz 160MHz 频宽 | 支持 | 受当地法规与 DFS 影响，雷达信道可能切频 |
| 802.11k（邻居报告） | 支持 | 默认关闭，需手动开启 |
| 802.11v（BSS 切换管理） | 支持 | 默认关闭，需手动开启 |
| 802.11r（快速漫游） | 支持 | 默认关闭，需手动配置，多 AP 漫游用 |
| Mesh（802.11s） | 待确认 | 驱动支持 mesh 点模式；加密 mesh 依赖 wpad 版本，底包默认值未核对 |
| LNA（低噪声放大器） | 待确认 | 属硬件配置，需核对板子 FEM 型号，固件不决定 |
| PA（功率放大器） | 待确认 | 同上 |
| BSS 染色（信道染色） | 支持 | 802.11ax 自带，随 11ax 开启 |
| MU-MIMO | 支持 | 下行；上行与多用户增益依赖终端支持 |
| 波束成型 | 支持 | 显式波束成型需终端反馈配合 |
| OFDMA | 支持 | 802.11ax 上下行 |
| WPA3 | 支持 | WPA3-Personal（SAE），配置里可选 |
| 1024-QAM | 支持 | 802.11ax 调制方式 |

## 底包（已确认）

| 项目 | 取值 |
|---|---|
| 底包 | [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma)，分支 `c3po-tag-8021q`（该仓库的默认分支） |
| 内核 | **6.18**（CR8806 参考发布为 6.18.55） |
| NSS feed | [kuncy7/nss-packages](https://github.com/kuncy7/nss-packages)，分支 `ipq50xx-rebase` |
| NSS 固件 | **12.5-210-MP**（默认）；备选 **12.2-156-MP.R** |
| 目标 | `qualcommax/ipq50xx` |
| 拓扑 | DSA（`nss.general.topology='dsa'`，底包默认） |

为什么选这套：它是目前唯一同时做到最新内核（6.18）又真正加速
IPQ5018 的树，且已有 CR8806 的 profile。官方 OpenWrt 25.12（6.12）
和 ImmortalWrt 25.12（6.12）都没有 NSS，只能当备选。
不要用 qosmio/openwrt-ipq 做 IPQ50xx NSS（其作者自述 IPQ50xx
补丁是“盲猜、至今未成功”），也不要用 hzyitc/LiBwrt 的
4.4/5.4/5.15 老树（5.15 没有 NSS NAT）。

关键约束（来自底包文档，照做不要自创）：

- `nss-tools-dwmac` 必须选 `=y`，不能是 `=m`，否则镜像启动后 NSS
  是静默不工作的（`fw_mask` 一直是 `0x0`，且没有任何报错）。
- 内核 flow offloading（flowtable）必须关：它会在 ECM 分类之前
  抢走已建立的 TCP 流，导致 ECM 永远看不到流，固件把每个包都
  异常送回 host，CPU 占用 30–60% 而不是 3–5%。
- 交换机桥上的 IGMP snooping 必须关（底包默认即关）。
- 驱动必须按所装固件的版本编译：12.5 的驱动配 12.2 的固件
  （或反过来）能通流量，但 Wi-Fi 计数器会一直是 0。

## 设备状态

| 设备 | 状态 | 说明 |
|---|---|---|
| CR8806（M79） | ✅ 基线，第一次编译成功 | 底包 `256m` 组已有 `xiaomi_cr8806` profile；本仓库的 `configs/cr8806-256m.config` 就是它的基线配置。256 MB 内存，Linux 可见约 169 MiB，空闲时只剩 20–30 MiB，大包要先算内存账；LuCI 已保留，若 OOM 先砍它。 |
| CR8808 / CR8809 | ⏳ 待上机实测 | 底包里 cr8806 这个 profile 自带 ALT0=CR8808、ALT1=CR8809（同 M79、同 DTS `config@mp02.1`、128 MB NAND），理论上同一个镜像就能认，不用单独移植；但必须上机实测，不能只凭 ALT 就承诺。 |
| m79 A / m79 B | ❓ 未定义 | **没有任何公开资料定义 M79 的 A/B 区别，底包里也没有 A/B 之分**（VARIANT 就是 M79）。不要假设一个 m79 镜像能通吃 A 和 B；实测时注意板子差异。 |
| m81 | ⏳ 待确认 | m79 / m81 是主板版本，不是型号；底包里没有 m81 profile，移植时不要直接把 CR8806（M79）的设置套上去。 |

以下在 CR8806 上明确**未测试**（不要在发布说明里承诺）：
NAT/路由模式吞吐、IPv6、多个 Wi-Fi 客户端、LED/按键、
SQM、dnsmasq 缓存的实际效果。

## 编译是怎么跑的

`.github/workflows/build-ipq50xx.yml`，手动触发
（`workflow_dispatch`），流程：

1. 克隆底包到 `base_ref` 指定的提交（默认是 2026-11-02 在底包
   主页上看到的 `c3po-tag-8021q` HEAD 提交）。
2. 恢复 ccache 缓存（`openwrt/.ccache`）。
3. `./scripts/feeds update -a && ./scripts/feeds install -a`，
   并检查 nss feed 里有 `qca-nss-drv`。
4. 从上游拉 Argon 主题和配置（底包 feed 里没有），并安装。
5. 把 `configs/<设备>.config` 拷成 `.config`，按 `firmware`
   输入选择 12.5 或 12.2，跑 `make defconfig`，然后逐项检查
   关键符号确实留下来了（符号名写错会被 defconfig 静默丢掉，
   这一步就是防这个）。
6. 把仓库 `files/` 打进镜像（首次开机脚本等），
   uci-defaults 脚本在镜像里需要可执行权限，工作流里处理。
7. `make download`，然后 `make -j$(nproc)`，失败自动退回
   `make -j1 V=s` 打详细日志。
8. 整理 artifacts：sysupgrade 镜像、factory 镜像、initramfs
   镜像（如果有）、`config.buildinfo`、`feeds.buildinfo`、
   `sha256sums.txt`；其中 sysupgrade 和 factory 是强制项，
   缺了就失败，不会发一个不完整的 Release。
9. 上传 artifacts，并发一个 Release（tag 是
   `设备-日期-运行号-尝试号`，每次运行一个独立 Release，
   重跑换新 tag）。
10. 删旧缓存、删旧工作流（保留 2 天），失败不影响任务。

触发参数：

- `device`：设备 profile，当前只有 `xiaomi_cr8806`。
- `firmware`：`12.5`（默认）或 `12.2`（备选）。注意驱动按固件
  版本编译，两个版本不要混用。
- `base_ref`：底包提交， rebase 时更新。

## 首次安装（CR8806）

- 首次安装走 UART（115200 8N1）+ TFTP，启动 initramfs
  （`config@mp02.1`），把 factory.ubi 写到另一个 slot；之后
  升级用 sysupgrade。
- 双 slot 写错有变砖风险，操作前确认自己板子的 slot 布局，
  不要照搬别板子的步骤；刷之前先备份原厂固件。
- 首次开机先在 LuCI 里设 root 密码（OpenWrt 默认 root 没密码）。

## 装好后怎么验证 NSS 真在工作

```sh
ls /etc/rc.d | grep S19nss
# 应该有 nss 服务

logread -e nss
# 最后应该出现 "NSS wired plane + ECM up"

cat /sys/kernel/debug/qca-dwmac-nss/status
# 端口应该显示 started

# 跑流量时：
cat /sys/kernel/debug/ecm/ecm_nss_ipv4/tcp_accelerated_count
# 应该 > 0

grep -m1 ipv4_rx_pkts /sys/kernel/debug/qca-nss-drv/stats/ipv4
# 应该持续上涨

nft list flowtables
# 应该什么都不输出（有 flowtable 说明 flow offloading 还开着，ECM 会被饿死）

top
# 满速流量下 idle 应该保持在 90% 以上
```

## 加设备

见 [docs/adding-devices.md](docs/adding-devices.md)。一句话概括：
先从硬件上把板子定义清楚（丝印、FEM、caldata），再到底包里做
profile/DTS，回来复制一份配置、往 workflow 矩阵里加一行、
上机跑一遍上面的冒烟测试。CR8808/CR8809 目前看不用移植，
先按 cr8806 同镜像实测。

## 合规说明

- 发布镜像时请一并附上当次编译的 `config.buildinfo` 和
  `feeds.buildinfo`（workflow 已经收集），这是 GPL 源码提供
  义务的一部分。
- NSS 固件是专有二进制 blob，不是开源软件，不要在宣传里
  把它说成开源；也不要把 blob 直接塞进本仓库，编译时由
  feed 链路获取。
- 各设备的校准数据（caldata）来自设备自己的 ART 分区，
  不要把别的板子的 caldata 拷进镜像。

## 未确认事项

- 底包提交 pin：workflow 默认的 `base_ref` 已核对为 `c3po-tag-8021q`
  的 HEAD 提交（2026-10-31），rebase 时更新。
- feed 钉住：仓库 `feeds.conf` 已钉住第 5 次编译的全部 feed 提交
  （packages 24f7c066、luci ae19cdfd、routing ea8633da、
  telephony 9bcb6d71、video 4582d70f、nss 4fa071ab），工作流在
  feeds update 前拷过去；之前 packages 和 luci 在第 1 次和第 5 次
  编译之间都动过，不钉住就无法复现。
- 新增的特性（Argon、SQM、SmartDNS、O3 等）已在第 5 次编译
  （2026-11-03）中编出并发布，上机实测仍待做；
  bridge-mgr 已确认不在 ipq50xx 上（见上），已从配置里去掉；
  Fullcone、luci-app-cpufreq、luci-app-arpbind 已确认不在钉住的
  feed 里（packages/net 在 18af3f1b 没有 fullcone，luci 在
  5599f42b 没有 cpufreq/arpbind），已从配置里去掉；不要在没
  核对 feed 的情况下把它们加回来。
  `.config` 里的符号名 workflow 会在 defconfig 后逐项核对，
  核对不过就失败，不会静默出一个缺功能的包。
- factory.ubi 的产出：按 UbiFit 默认规则会产，工作流已把它
  列为强制 artifact，下次编译验证。
- CR8806 上机功能（NAT/IPv6/多客户端/WiFi/SQM/
  dnsmasq 缓存）尚未实测。
- m79 A/B 的区别仍无公开定义。
