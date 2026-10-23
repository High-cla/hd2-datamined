# 文档索引

> 32 篇文档按**类型**分到 6 个子目录（2026-10-23 重排；文件名一律未改，历史可用 `git log --follow` 追）。
> 事实类文档文件名带 build 号，结论只对那个 build 成立；方法类文档不带 build 号，跨 build 有效。
> 当前验证 build：`26088801` ｜ 历史基线：`25480438` → `25988413`。
> 每个 build 验证了什么、新 build 到手先跑哪三步 —— 见 **[../BUILDS.md](../BUILDS.md)**。
> 链接自检：`python tools/check_links.py`。

**★ 只想动手改一张表**：看 [FILE-ROUTE-WORKFLOW-26088801](cases/FILE-ROUTE-WORKFLOW-26088801.md)
（八步流程 + 锚点哈希 + 16 条坑）；要交给代理自动做，用技能
[`skills/hd2-file-route-mod`](../skills/hd2-file-route-mod/SKILL.md)。

**★ 优先读（结论最硬、复用价值最高）**：
[TABLE-DICTIONARY](tables/TABLE-DICTIONARY-25988413.md) ·
[ENTITY-TABLE](tables/ENTITY-TABLE-25988413.md) ·
[EXPLOSION-VISUAL](explosions/EXPLOSION-VISUAL-26088801.md) ·
[EXPLOSION-PROJECTILE](explosions/EXPLOSION-PROJECTILE-25988413.md) ·
[STRATAGEM-SETTINGS-DECODED](tables/STRATAGEM-SETTINGS-DECODED.md) ·
[STRATAGEM-FIELDS](tables/STRATAGEM-FIELDS-26088801.md) ·
[WEAPON-CUSTOMIZATION-DECODED](tables/WEAPON-CUSTOMIZATION-DECODED.md) ·
[LOADER-SPEC](engine/LOADER-SPEC-25988413.md)

| 类别 | 放什么 | 篇数 |
|---|---|---:|
| `builds/` | 每个 build 的总体变化、差异、路线取舍 | 4 |
| `engine/` | 引擎侧：格式封装、API 面、Lua 运行时、探针、加载器 | 9 |
| `tables/` | 数据表与实体库的解码 / 改写 | 9 |
| `explosions/` | 爆炸与弹头（玩法层 + 外观层） | 2 |
| `boundaries/` | 被挡住的路：进程内存、虚拟机 | 2 |
| `cases/` | 案例与外部参照：社区包、贴图委托、wiki 数据 | 7 |

---

## builds/ —— 每个 build 变了什么

| 文档 | 一句话内容 | build |
|---|---|---|
| [BUILD-25988413.md](builds/BUILD-25988413.md) | 10-20 更新到底改了什么：文件身份、代码与资源层的变化、更新后工具链还剩什么能用 | `25988413` |
| [BUILD-26088801-DIFF.md](builds/BUILD-26088801-DIFF.md) | 7.2.1 hotfix 逐层比对：55 张表一张没变，变的是 exe/game.dll 与 bundle 打包（含一次误报的复盘） | `26088801`（对比 `25988413`） |
| [ROUTES-COMPARE-26088801.md](builds/ROUTES-COMPARE-26088801.md) | 战备线与护甲线谁先开：四个判据逐项对照，结论先开战备线 | `26088801` |
| [PATCH-SALVAGE-25988413.md](builds/PATCH-SALVAGE-25988413.md) | 22 个旧补丁按资源类型清点：每个都带 lua，资产只能当原料，外观方向是新活不是抢救 | `25988413` |

## engine/ —— 引擎与运行时

格式封装、API 面、Lua 运行时、探针写法、加载器规格。

| 文档 | 一句话内容 | build |
|---|---|---|
| [DLBIN-SEALED-BOX.md](engine/DLBIN-SEALED-BOX.md) | `.dl_bin` 的封装模型：48 B 头 + `crypto_box_seal` 形态、keystream 关系，以及仍然打不开的那一段 | `25988413` |
| [ENGINE-API-25988413.md](engine/ENGINE-API-25988413.md) | 内存路全死之后引擎侧还能读到什么：`world:units()` / `Unit.world_*` 的能读与不能读，逐条三态 | `25988413` |
| [STINGRAY-API-25988413.md](engine/STINGRAY-API-25988413.md) | 游戏内 `pairs()` 枚举到的 446 个 Stingray 入口，并纠正"只开了 19 个命名空间"的读法 | `25988413` |
| [LUA-API-25988413.md](engine/LUA-API-25988413.md) | 机器枚举的 Lua API 全量面：125 个命名空间 / 2,483 个成员（2026-10-21 重跑） | `25988413` |
| [LUA51-TOOLING-25988413.md](engine/LUA51-TOOLING-25988413.md) | `lua51.dll` 消失后，从 LuaJIT 宿主迁到 stock Lua 5.1 要改哪些工具与判据 | `25988413` |
| [PROBE-AUTHORING-25988413.md](engine/PROBE-AUTHORING-25988413.md) | 新 build 上怎么写探针：旧探针为什么"能加载但静默失效"，以及自检的正确姿势 | `25988413` |
| [GUI-HUD-25988413.md](engine/GUI-HUD-25988413.md) | 纯 Lua 能不能自己画屏幕文字：三次崩溃换来的 `Gui.*` 真实签名与可用绘制路径 | `25988413` |
| [LOADER-SPEC-25988413.md](engine/LOADER-SPEC-25988413.md) | 新的共享加载器必须满足什么，含 `package.loadlib` + 原生 DLL 这条路的最终否证 | `25988413` |
| [PATCH-LOADER-DESIGN-26088801.md](engine/PATCH-LOADER-DESIGN-26088801.md) | 数据文件路线不需要执行权：用离线合成器替掉 boot 覆盖 + 运行时发现 | `26088801` |

## tables/ —— 数据表与实体库

| 文档 | 一句话内容 | build |
|---|---|---|
| ★ [TABLE-DICTIONARY-25988413.md](tables/TABLE-DICTIONARY-25988413.md) | **全表字典**：55 张表的组/行数/步长/尾块几何 + 类型库字段偏移（1,208 类型 / 7,349 成员），查字段从这篇进 | `25988413` |
| ★ [ENTITY-TABLE-25988413.md](tables/ENTITY-TABLE-25988413.md) | 47 MB 实体库的离线改写：组件块布局、内容哈希闸门、校正字、`fnid=8` 可选弹种，以及 LoadoutEntry 否证 | `25988413` |
| [ENTITY-LOCID-26088801.md](tables/ENTITY-LOCID-26088801.md) | 实体库的本地化 ID 字段：实体 → 游戏内名字的唯一出处（`EncyclopediaEntry` 块，643 行可解） | `26088801`（明文同 `25988413`） |
| [LOCID-NAMES-25988413.md](tables/LOCID-NAMES-25988413.md) | 表行里存的是 32 位本地化 ID：`.strings` 全局 ID→文本表怎么打通六张表的名字 | `25988413` |
| [ROW-NAMING-25988413.md](tables/ROW-NAMING-25988413.md) | 表内逐行名字的两条取法（指针法 vs 位置法）、判据，以及位置法取错过名的两张表 | `25988413` |
| ★ [WEAPON-CUSTOMIZATION-DECODED.md](tables/WEAPON-CUSTOMIZATION-DECODED.md) | 武器配件总表：88 B 行结构、九类槽位枚举、252 行逐行可读导出 | `25988413` |
| ★ [STRATAGEM-SETTINGS-DECODED.md](tables/STRATAGEM-SETTINGS-DECODED.md) | 战备表：400 B 行 / 12 组，`+104` 冷却与 `+80` 次数，含三处旧结论的自我否证 | `25988413` |
| ★ [STRATAGEM-FIELDS-26088801.md](tables/STRATAGEM-FIELDS-26088801.md) | 战备字段总表：**呼叫时间/冷却面板公式**（先预测后实测）、散布 `+0x24` 实机、条目 ID 重复=崩溃、`+0x3C` 不是轮数 | `26088801` |
| [STRATAGEM-REFERENCE-CHAIN-25988413.md](tables/STRATAGEM-REFERENCE-CHAIN-25988413.md) | 战备→弹丸→爆炸这条链：表内只有弹丸↔爆炸一跳，战备→弹丸是否证 | `25988413` |

## explosions/ —— 爆炸与弹头

| 文档 | 一句话内容 | build |
|---|---|---|
| ★ [EXPLOSION-PROJECTILE-25988413.md](explosions/EXPLOSION-PROJECTILE-25988413.md) | 玩法层：换弹头整行、改 `+144`/`+156` 换爆炸、改 `+80`/`+84` 加破片 | `25988413` |
| ★★ [EXPLOSION-VISUAL-26088801.md](explosions/EXPLOSION-VISUAL-26088801.md) | 外观层：粒子 `+0x38`、震屏 `+0x28`、整行克隆，以及 `+0xA8` 这个纯数据的跨包加载杠杆 | `26088801` |

## boundaries/ —— 被挡住的路

| 文档 | 一句话内容 | build |
|---|---|---|
| [MEMORY-ACCESS-25988413.md](boundaries/MEMORY-ACCESS-25988413.md) | 进程内外的内存路还剩什么：EAC 剥掉 `PROCESS_VM_READ`、`ffi` 消失，DLL 加载两道闸门的实测 | `25988413` |
| [VM-DUMP-25988413.md](boundaries/VM-DUMP-25988413.md) | 虚拟机路线：宿主读 guest 内存已证实，但过不了 EAC 的虚拟机检测 | `25988413` |

## cases/ —— 案例与外部参照

| 文档 | 一句话内容 | build |
|---|---|---|
| ★ [FILE-ROUTE-WORKFLOW-26088801.md](cases/FILE-ROUTE-WORKFLOW-26088801.md) | **改盘上数据的完整工作流**：密封盒 + 内容哈希两层、4 张表的锚点哈希、校正字宿主的三种选择（含三次崩溃的归因）、八步命令链、EAGLE 双行案例、16 条坑 —— 想动手改表从这篇进 | `26088801`（流程跨 build） |
| [CASE-STUDY-20261021.md](cases/CASE-STUDY-20261021.md) | 三个社区包拆解出来的路：`.patch_N` 能替换任意资源类型，纯资产 mod 不需要 loader | `25988413` |
| [TEXTURE-SWAP-10X-APEX.md](cases/TEXTURE-SWAP-10X-APEX.md) | 一次贴图替换委托：BC1 往返误差、材质槽判定、`patch_3` 部署与回滚 | 跨 build |
| [COMMUNITY-MODS-COMPAT-26088801.md](cases/COMMUNITY-MODS-COMPAT-26088801.md) | SSEO 与护甲多被动为何不能共存：争的是同一文件的基线所有权，不是加载顺序 | `26088801` |
| [PRIOR-ART-NAMING.md](cases/PRIOR-ART-NAMING.md) | 别人怎么把内部名接到显示名/页面（filediver / HD2Runtime / wiki 模块），我们该借哪一个 | 跨 build |
| [WIKI-DATA-MODULES.md](cases/WIKI-DATA-MODULES.md) | wiki `Module:` 命名空间里的原始解码数据清单，以及每份能补哪张表的字段名 | 跨 build |
| [WIKI-LOCAL-DB.md](cases/WIKI-LOCAL-DB.md) | 不抓 HTML：页面源码 + JSON 模块落成本地 SQLite，一条命令查战备/武器全貌 | 跨 build |

---

## 附录 A：能力明细（自根 `README.md` 迁入，逐条保留）

| 能力 | 状态 |
|---|---|
| 解开 `data/game/*.dl_bin` 的封装（`crypto_box_seal` 形态）并还原明文 | ✓ 工具可跑（需自备你自己的密钥材料，见根 README） |
| 还原**内容哈希闸门**（MurmurHash64A + 校正字），改完字节仍能通过校验 | ✓ 已实机 |
| `generated_entities.dl_bin`：组件块布局 / hashmap / 行结构 | ✓ 已实机 |
| 武器数值：人机、站姿惩罚、散布、后坐、装填可移动 | ✓ 已实机 |
| **可选弹种**：`fnid=8` + 备选弹丸（伤害+状态切换） | ✓ 已实机（眩晕 / 燃烧） |
| **独立弹药池**：`fnid=4` + `WeaponRounds` 两套弹丸（各带弹道、各自弹匣/备弹） | ✓✓ 已实机（仅限原生有该行的 25 把） |
| **爆炸/弹头线**：换弹头整行 · 换爆炸（`+144`/`+156`）· **加破片（`+80`/`+84`）** | ✓✓ 已实机 |
| **爆炸视觉 + 资源加载**：整行克隆供体爆炸 · `+0xA8` = 纯数据的「跨包加载」杠杆（任意外观可移植） | ✓✓ 已实机（`26088801`） |
| 自制伤害行（占无主行，写伤害/穿甲/状态强度） | ✓ 离线门禁通过 |
| 解锁未发布物品（`LoadoutEntry.selectable`） | ✗ 已否证（发布数据里没有这个开关） |

## 附录 B：已验证的核心结论（自根 `README.md` 迁入）

> 下面这些是**在 25988413 上做的实机/离线验证**；其中结构层部分（密封盒、栅门算法、块布局、行命名、本地化 ID）
> 在 26088801 上已复验仍成立，但**每个具体偏移都必须按 [../BUILDS.md](../BUILDS.md) §3 的步骤在你自己的 build 上重验一遍**。

1. **闸门**：`data/game/*.dl_bin` 的明文被 `game.dll` 里烘焙的 MurmurHash64A 校验（seed `0xDEADBEEFABAD1DEA`），不匹配就 `0xC000000D`。**解法**：改完字节后在文件内一个语义惰性的 8 字节对齐空位解出"校正字"，让哈希回到原值 —— 文件长度不变、内容校验通过。
2. **实体库不是 toc，是块序列**：`u32 type | 'LDLD' | ver | type | payload | ...`（28 B 头）；组件块 payload = `[hashmap][行数组]`；hashmap 键 = `Murmur64A(资源路径)`。
3. **可选弹种两格**：`WeaponData +184`（`FunctionInfo.function_id`，**8 = 引擎原生 ProgrammableAmmo**）＋ `ProjectileWeapon +576`（**备选弹丸 type id**）。备选弹**只贡献伤害+状态**，弹道来自主弹行。
4. **独立弹药池**：`WeaponRoundsComponentData`，行内 `+64` = 两个弹丸 id、`+72` = 两个弹匣容量、`+80` = 两个备弹；全表 25 把里**只有 SG-20 Halt 是 B≠A，也正好只有它是 `fnid=4`**。
   **实机**（SG-8 Punisher：`fnid` 0→4、`rounds_b` 264→140）：能切弹、两个池独立、B 池自带弹道（霰弹枪变单颗）✓✓
   **正向配方**（SG-97 Sweeper，实机 ✓✓）：`fnid`0→4 + `rounds_b`=352(Cookout 燃烧弹) + `mag_b`=7 + `flag(+104)`=1 + `+108` 六个 hash 照抄双池武器 → 切到 B 得到 **20 颗燃烧弹丸**，两个弹匣各 7 发且独立、备弹 70 共用。
   **边界**：只对**原生自带 `WeaponRounds` 行**的 25 把武器有效。给「整匣换弹」武器新增该行（AR-23，四次变体）**全部在打开切弹页面时崩溃** ✗ —— 见 [ENTITY-TABLE-25988413.md](tables/ENTITY-TABLE-25988413.md) §9.7。
5. **未发布物品**：`LoadoutEntryComponentData` 只有 `{id, type, dlc_pack_id, equipment_tags[5]}` 32 字节，**没有 selectable**；带 selectable 的结构在发布数据里 0 命中 ⇒ 不是离线可翻的开关。
