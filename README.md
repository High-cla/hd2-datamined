# Helldivers 2 · 离线数据表逆向笔记与工具

> **当前验证 build：`26088801`**（2026-10-22 hotfix）｜历史基线：`25480438` → `25988413`｜文档重排 2026-10-23。
>
> 本仓库不绑定某个 build。结构层结论（密封盒、内容哈希、`LDLD` 组头、实体块布局、
> `.strings` 与本地化 ID 机制、行命名机制）实测跨 build 有效；**偏移/地址类结论必须逐 build 复验**，
> 所以事实类文档都带 build 号。新 build 到手先跑哪三步、每个 build 验证了什么 —— 见 **[BUILDS.md](BUILDS.md)**。

## 这是什么

一套**离线**（改数据文件，不碰进程内存、不需要 Lua/FFI/注入）的 Helldivers 2 数据表研究笔记与工具。

| 能力 | 状态 |
|---|---|
| 解封 `data/game/*.dl_bin` 并还原明文（`crypto_box_seal` 形态，需自备密钥材料） | ✓ 工具可跑 |
| 保内容哈希改写：MurmurHash64A + 校正字，改完字节仍过闸门 | ✓ 已实机 |
| 实体库 / 组件块 / 行结构解析与离线改写 | ✓ 已实机 |
| 武器：数值（人机·站姿·散布·后坐·装填可移动）/ 可选弹种 / 独立弹药池 / 自制伤害行 | ✓ 已实机（弹药池仅限原生有该行的 25 把） |
| 爆炸·弹头：换弹头整行 / 换爆炸（`+144`/`+156`）/ 加破片（`+80`/`+84`） | ✓✓ 已实机 |
| 爆炸视觉：整行克隆 + `+0xA8` 跨包加载（任意外观可移植） | ✓✓ 已实机（`26088801`） |
| 战备：呼叫时间 / 冷却 / 散布 / 使用次数（含面板公式：基础值 × 升级、+ 交付延迟） | ✓✓ 已实机（`26088801`） |
| 全表字典：55 张表的几何 + 类型库字段偏移（1,208 类型 / 7,349 成员） | ✓ 离线可复现 |
| 解锁未发布物品（`LoadoutEntry.selectable`） | ✗ 已否证（发布数据里没有这个开关） |

逐条证据见 **[docs/README.md](docs/README.md)**；核心结论（闸门算法、实体块布局、可选弹种、独立弹药池、
LoadoutEntry 否证）连原文一起放在该页 **附录 B**。

## 不是什么

- **不包含任何游戏资产、明文表以外的游戏内容、密钥、密钥材料**。`tables/` 只有三张很小的参数表（合计 ~180 KB），用于验证解析器。
- 不提供"解除封锁/解锁付费内容/破坏他人游戏"的方法。已证否的路线也如实写"否证"。
- **不提供在游戏进程内加载未签名 DLL 的方法** —— 不是没写，是实测走不通：加载器只映射它自己带的映像，
  未签名 `577`、签名但不在名单 `193`、自签并装进 `LocalMachine\Root` 仍然 `577`
  （[MEMORY-ACCESS-25988413.md §12](docs/boundaries/MEMORY-ACCESS-25988413.md)）。想绕开它只能动反作弊本身，不做。
- 不是通用 mod 管理器；mod 打包/安装请用社区工具。

## 目录

```
BUILDS.md  每个 build 验证了什么、哪些结论跨 build 有效、新 build 到手先跑的三步
docs/      31 篇文档，按类型分 6 个目录（逐篇索引见 docs/README.md）
           builds/  每个 build 变了什么         engine/     格式封装 · API 面 · Lua · 探针 · 加载器
           tables/  数据表与实体库              explosions/ 爆炸与弹头
           boundaries/ 被挡住的路（内存/虚拟机）  cases/      案例与外部参照
tools/     离线工具链（解析 / 改字节 / 保哈希 / 行级编辑 + 门禁；索引与依赖见 tools/README.md）
tables/    三张小参数表（damage / projectile / weapon_customization），仅供解析验证
refs/      字段图与索引：行名 / 本地化名 / 爆炸弹头引用链 / 表几何 / 武器键→名字 / 275 个组件块类型名
examples/  最小解析示例（纯标准库）+ 字段说明
```

## 快速开始（核心表工具：纯 Python 3.11+，无第三方依赖）

> 少数**可选**工具需要第三方包（PyNaCl / Pillow / lupa / `srkit`），依赖与验证状态见 **[tools/README.md](tools/README.md)**。

```bash
# 1) 解析一张表（不需要游戏文件也能跑仓库里 tables/ 的那三张）
python examples/parse_examples.py --projectile tables/generated_projectile_settings.dl_bin
python examples/parse_examples.py --blocks     refs/../tables/...   # 见脚本内注释

# 2) 算一个文件的 Murmur64A（内容哈希闸门用的那个）
python tools/murmur64.py <file>

# 3) 组件块/字段：275 个块类型名在 refs/entity-block-types.json
python - <<'PY'
import json; d=json.load(open('refs/entity-block-types.json'))
for b in d['blocks']:
    if b['component'] and 'Weapon' in b['component']: print(b)
PY
```

动自己机器上的游戏文件时，标准流程见 **[ENTITY-TABLE-25988413.md §5](docs/tables/ENTITY-TABLE-25988413.md)**
（取明文 → 改字节 → 解校正字 → 校验哈希 → 重新封装 → 回读）。改完文档跑一次
`python tools/check_links.py` 自检链接（0 断链才算过）。

## 文档索引

`docs/` 下按类型分 6 类，逐篇索引（每篇一句话 + 适用 build）在 **[docs/README.md](docs/README.md)**：

| 类别 | 放什么 | 篇数 |
|---|---|---:|
| `docs/builds/` | 每个 build 的总体变化、差异、路线取舍 | 4 |
| `docs/engine/` | 引擎侧：格式封装、API 面、Lua 运行时、探针、加载器 | 9 |
| `docs/tables/` | 数据表与实体库的解码 / 改写 | 8 |
| `docs/explosions/` | 爆炸与弹头（玩法层 + 外观层） | 2 |
| `docs/boundaries/` | 被挡住的路：进程内存、虚拟机 | 2 |
| `docs/cases/` | 案例与外部参照：社区包、贴图委托、wiki 数据 | 6 |

## 相关仓库

- **[hd2-srkit](https://github.com/deepseekv41flash/hd2-srkit)** —— Stingray/HD2 资源解包打包工具（纯标准库，资源层：toc/bundle/DSAR、unit/texture/material/lua、空 unit 模板）。本仓库里的 `tools/` 是**数据表**层面的实验脚本，两者互补。
  > 它**不**包含运行期内存改写与 Lua addon 构建管线 —— 那些在 build 25988413 已不可用（Lua 无 `ffi` + EAC 拒绝外部读内存），不发布以免误导。

## 免责声明

- 仅供**单人/私人环境**的研究与学习。改动数据文件可能违反游戏服务条款，也可能导致崩溃、存档异常、或与他人的联机体验异常。
- **不要**在多人游戏中使用会改变他人体验的改动；不要分发改过的游戏数据。
- 所有结论都标注了三态：`✓ 实机` / `✗ 否证` / `⚠ 未证`。游戏更新后（build 变化）偏移与哈希会整体失效 —— 本仓库不保证跨版本。

## 许可证

[MIT License](LICENSE) —— 代码、文档、索引一并用 MIT。结论记录日期 2026-10-22；游戏 build `26088801`。
