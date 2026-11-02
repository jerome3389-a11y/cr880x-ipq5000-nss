# ipq50xx-openwrt-nss

IPQ50xx 设备的 OpenWrt 固件自动编译项目：用 GitHub Actions 自动编译带
Qualcomm NSS 硬件加速的固件，目标是**最新内核 + 最强 NSS 加速**。

> 本仓库只放编译脚本和配置，不放底包源码。编译时 workflow 会从底包仓库
> 克隆指定提交的代码再编译。**本脚手架尚未经过实际编译验证**，第一次
> 运行前请先看“未确认事项”。

## 底包（已确认）

| 项目 | 取值 |
|---|---|
| 底包 | [kuncy7/openwrt-nss-edma](https://github.com/kuncy7/openwrt-nss-edma)，分支 `c3po-tag-8021q`（该仓库的默认分支） |
| 内核 | **6.18**（CR8806 参考发布为 6.18.55） |
| NSS feed | [kuncy7/nss-packages](https://github.com/kuncy7/nss-packages)，分支 `ipq50xx-rebase` |
| NSS 固件 | **12.5-210-MP**（默认）；备选 **12.2-156-MP.R** |
| 目标 | `qualcommax/ipq50xx` |
| 拓扑 | DSA（`nss.general.topology='dsa'`，底包默认） |
| 发布形式 | sysupgrade 镜像（底包发布即如此）；首次安装见下 |

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
| CR8806（M79） | ✅ 基线已就绪 | 底包 `256m` 组已有 `xiaomi_cr8806` profile；本仓库的 `configs/cr8806-256m.config` 就是它的基线配置。256 MB 内存，Linux 可见约 169 MiB，空闲时只剩 20–30 MiB，大包要先算内存账。 |
| CR8808（M79 / M81） | ⏳ 待用户移植 | 底包和 fanha99 分支都明确“未测试”。CR8808 同时存在 M79 和 M81 两种主板，必须按板子分开做。 |
| CR8809（多为 M79） | ⏳ 待用户移植 | 同上，未测试；移植前要先核对 FEM / caldata 是否与 CR8806 一致。 |
| m79 A / m79 B | ❓ 未定义 | **没有任何公开资料定义 M79 的 A/B 区别。** 不要假设一个 m79 镜像能通吃 A 和 B；必须先从硬件（丝印、FEM 型号、ART 数据）定义清楚再写配置。 |
| m81 | ⏳ 待用户移植 | m79 / m81 是主板版本，不是型号。m81 更接近 Redmi AX3000 全球版的行为，移植时不要直接把 CR8806（M79）的设置套上去。 |

以下在 CR8806 上明确**未测试**（fanha99 README 原话），不要在发布
说明里承诺：NAT/路由模式吞吐、IPv6、多个 Wi-Fi 客户端、
LED/按键、CR8808/CR8809。

## 编译是怎么跑的

`.github/workflows/build-ipq50xx.yml`，手动触发
（`workflow_dispatch`），流程：

1. 克隆底包到 `base_ref` 指定的提交（默认是 2026-11-02 在底包
   主页上看到的 `c3po-tag-8021q` HEAD 提交）。
2. `./scripts/feeds update -a && ./scripts/feeds install -a`，
   并检查 nss feed 里有 `qca-nss-drv`。
3. 把 `configs/<设备>.config` 拷成 `.config`，按 `firmware`
   输入选择 12.5 或 12.2，跑 `make defconfig`，然后逐项检查
   关键符号确实留下来了（符号名写错会被 defconfig 静默丢掉，
   这一步就是防这个）。
4. `make download`，然后 `make -j$(nproc)`，失败自动退回
   `make -j1 V=s` 打详细日志。
5. 上传 artifacts，并发一个 Release：sysupgrade 镜像、
   initramfs 镜像（如果有）、`config.buildinfo`、
   `feeds.buildinfo`、`sha256sums.txt`。Release 的 tag 是
   `设备-日期-运行号-尝试号`，每次运行一个独立 Release，
   重跑换新 tag。

触发参数：

- `device`：设备 profile，当前只有 `xiaomi_cr8806`。
- `firmware`：`12.5`（默认）或 `12.2`（备选）。注意驱动按固件
  版本编译，两个版本不要混用。
- `base_ref`：底包提交， rebase 时更新。

## 首次安装（CR8806）

- 首次安装走 UART（115200 8N1）+ TFTP，启动 initramfs
  （`config@mp02.1`），把 factory.ubi 写到另一个 slot；之后
  升级用 sysupgrade。底包的发布本身是 sysupgrade-only。
- 双 slot 写错有变砖风险，操作前确认自己板子的 slot 布局，
  不要照搬别板子的步骤。

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
上机跑一遍上面的冒烟测试。

## 合规说明

- 发布镜像时请一并附上当次编译的 `config.buildinfo` 和
  `feeds.buildinfo`（workflow 已经收集），这是 GPL 源码提供
  义务的一部分。
- NSS 固件是专有二进制 blob，不是开源软件，不要在宣传里
  把它说成开源；也不要把 blob 直接塞进本仓库，编译时由
  feed 链路获取。
- 各设备的校准数据（caldata）来自设备自己的 ART 分区，
  不要把别的板子的 caldata 拷进镜像。

## 未确认事项（第一次编译前必须对上）

- 底包提交 pin：workflow 默认的 `base_ref` 已核对为 `c3po-tag-8021q`
  的 HEAD 提交（2026-10-31），rebase 时更新。
- nss feed 目前只 pin 了分支（底包的 `feeds.conf.default` 就是
  这样），还没 pin 到具体提交；拿到一次已知良好的编译后，
  把 `feeds.buildinfo` 里的 nss 行写进 `feeds.conf` 再提交。
- `.config` 里的符号名来自调研报告，workflow 会在 defconfig
  后逐项核对，核对不过就失败，不会静默出一个没 NSS 的包。
- CR8808/CR8809 的闪存布局（是否为 128 MB NAND 双 slot）
  目前只是按家族推测，未按型号确认，移植时必须实测。
