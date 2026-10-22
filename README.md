# Helldivers 2 · 离线数据表逆向笔记与工具

> **当前验证 build：`26088801`**（2026-10-22 hotfix）｜历史基线：`25480438` → `25988413`。
>
> 本仓库不绑定某个 build。结构层结论（密封盒、内容哈希、`LDLD` 组头、实体块布局、
> `.strings` 与本地化 ID 机制、行命名机制）实测跨 build 有效；**偏移/地址类结论必须逐 build 复验**，
> 所以事实类文档都带 build 号（`docs/xxx-25988413.md`）。
> 每个 build 验证了什么、哪些还能直接用、新 build 到手先跑哪三步 —— 见 **[BUILDS.md](BUILDS.md)**。

## 这是什么

一套**离线**（改数据文件，不碰进程内存、不需要 Lua/FFI/注入）的 Helldivers 2 数据表研究笔记与工具：

| 能力 | 状态 |
|---|---|
| 解开 `data/game/*.dl_bin` 的封装（`crypto_box_seal` 形态）并还原明文 | ✓ 工具可跑（需自备你自己的密钥材料，见下） |
| 还原**内容哈希闸门**（MurmurHash64A + 校正字），改完字节仍能通过校验 | ✓ 已实机 |
| `generated_entities.dl_bin`：组件块布局 / hashmap / 行结构 | ✓ 已实机 |
| 武器数值：人机、站姿惩罚、散布、后坐、装填可移动 | ✓ 已实机 |
| **可选弹种**：`fnid=8` + 备选弹丸（伤害+状态切换） | ✓ 已实机（眩晕 / 燃烧） |
| **独立弹药池**：`fnid=4` + `WeaponRounds` 两套弹丸（各带弹道、各自弹匣/备弹） | ✓✓ 已实机（仅限原生有该行的 25 把） |
| **爆炸/弹头线**：换弹头整行 · 换爆炸（`+144`/`+156`）· **加破片（`+80`/`+84`）** | ✓✓ 已实机 |
| 自制伤害行（占无主行，写伤害/穿甲/状态强度） | ✓ 离线门禁通过 |
| 解锁未发布物品（`LoadoutEntry.selectable`） | ✗ 已否证（发布数据里没有这个开关） |

## 不是什么

- **不包含任何游戏资产、明文表以外的游戏内容、密钥、密钥材料**。仓库里的 `tables/` 只有三张很小的参数表（合计 ~180 KB），用于验证解析器。
- 不提供"解除封锁/解锁付费内容/破坏他人游戏"的方法。已证否的路线也如实写"否证"。
- **不提供在游戏进程内加载未签名 DLL 的方法**——不是没写，是实测走不通：加载器只映射它自己带的映像，
  未签名 `577`、签名但不在名单 `193`、自签并装进 `LocalMachine\Root` 仍然 `577`
  （[MEMORY-ACCESS-25988413.md §12](docs/MEMORY-ACCESS-25988413.md)）。想绕开它只能动反作弊本身，不做。
- 不是通用 mod 管理器；mod 打包/安装请用社区工具。

## 目录

```
BUILDS.md  每个 build 验证了什么、哪些结论跨 build 有效、新 build 到手先跑的三步
docs/      27 篇文档：带 build 号的是"该 build 上实测的事实"，不带的是方法论（密封盒 / 命名 / wiki / 案例）
tools/     离线工具链（解析、改字节、保哈希、行级编辑 + 门禁；索引与可选依赖见 tools/README.md）
tables/    三张小参数表（damage / projectile / weapon_customization），仅供解析验证
refs/      字段图与索引：行名 / 本地化名 / 爆炸弹头引用链 / 表几何 / 武器键→名字 / 275 个组件块类型名
examples/  最小解析示例（纯标准库）+ 字段说明
```

## 快速开始（核心表工具：纯 Python 3.11+，无第三方依赖）

> 少数**可选**工具需要第三方包：PyNaCl（`dlbin_*`）、Pillow（贴图）、lupa（真 Lua 5.1）、
> `srkit`（构建补丁）。每个工具的依赖与验证状态见 **[tools/README.md](tools/README.md)**。

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

要动自己机器上的游戏文件时，标准流程见 **`docs/ENTITY-TABLE-25988413.md` §5**（取明文 → 改字节 → 解校正字 → 校验哈希 → 重新封装 → 回读）。

## 已验证的核心结论（都在文档里有原始输出）

> 下面这些是**在 25988413 上做的实机/离线验证**；其中结构层部分（密封盒、栅门算法、块布局、行命名、本地化 ID）
> 在 26088801 上已复验仍成立，但**每个具体偏移都必须按 [BUILDS.md](BUILDS.md) §3 的步骤在你自己的 build 上重验一遍**。

1. **闸门**：`data/game/*.dl_bin` 的明文被 `game.dll` 里烘焙的 MurmurHash64A 校验（seed `0xDEADBEEFABAD1DEA`），不匹配就 `0xC000000D`。**解法**：改完字节后在文件内一个语义惰性的 8 字节对齐空位解出"校正字"，让哈希回到原值 —— 文件长度不变、内容校验通过。
2. **实体库不是 toc，是块序列**：`u32 type | 'LDLD' | ver | type | payload | ...`（28 B 头）；组件块 payload = `[hashmap][行数组]`；hashmap 键 = `Murmur64A(资源路径)`。
3. **可选弹种两格**：`WeaponData +184`（`FunctionInfo.function_id`，**8 = 引擎原生 ProgrammableAmmo**）＋ `ProjectileWeapon +576`（**备选弹丸 type id**）。备选弹**只贡献伤害+状态**，弹道来自主弹行。
4. **独立弹药池**：`WeaponRoundsComponentData`，行内 `+64` = 两个弹丸 id、`+72` = 两个弹匣容量、`+80` = 两个备弹；全表 25 把里**只有 SG-20 Halt 是 B≠A，也正好只有它是 `fnid=4`**。
   **实机**（SG-8 Punisher：`fnid` 0→4、`rounds_b` 264→140）：能切弹、两个池独立、B 池自带弹道（霰弹枪变单颗）✓✓
   **正向配方**（SG-97 Sweeper，实机 ✓✓）：`fnid`0→4 + `rounds_b`=352(Cookout 燃烧弹) + `mag_b`=7 + `flag(+104)`=1 + `+108` 六个 hash 照抄双池武器 → 切到 B 得到 **20 颗燃烧弹丸**，两个弹匣各 7 发且独立、备弹 70 共用。
   **边界**：只对**原生自带 `WeaponRounds` 行**的 25 把武器有效。给「整匣换弹」武器新增该行（AR-23，四次变体）**全部在打开切弹页面时崩溃** ✗ —— 见 `docs/ENTITY-TABLE-25988413.md` §9.7。
5. **未发布物品**：`LoadoutEntryComponentData` 只有 `{id, type, dlc_pack_id, equipment_tags[5]}` 32 字节，**没有 selectable**；带 selectable 的结构在发布数据里 0 命中 ⇒ 不是离线可翻的开关。

## 相关仓库

- **[hd2-srkit](https://github.com/deepseekv41flash/hd2-srkit)** —— Stingray/HD2 资源解包打包工具（纯标准库，资源层：toc/bundle/DSAR、unit/texture/material/lua、空 unit 模板）。本仓库里的 `tools/` 是**数据表**层面的实验脚本，两者互补。
  > 它**不**包含运行期内存改写与 Lua addon 构建管线 —— 那些在 build 25988413 已不可用（Lua 无 `ffi` + EAC 拒绝外部读内存），不发布以免误导。

## 免责声明

- 仅供**单人/私人环境**的研究与学习。改动数据文件可能违反游戏服务条款，也可能导致崩溃、存档异常、或与他人的联机体验异常。
- **不要**在多人游戏中使用会改变他人体验的改动；不要分发改过的游戏数据。
- 所有结论都标注了三态：`✓ 实机` / `✗ 否证` / `⚠ 未证`。请按标记判断可信度。
- 游戏更新后（build 变化）偏移与哈希会整体失效 —— 本仓库不保证跨版本。

## 许可证

[MIT License](LICENSE) —— 代码、文档、索引一并用 MIT。

## 版本

- 记录日期：2026-10-22
- 游戏 build：25988413
- 详细结论与原始输出：`docs/ENTITY-TABLE-25988413.md`、`docs/DLBIN-SEALED-BOX.md`、`docs/BUILD-25988413.md`
