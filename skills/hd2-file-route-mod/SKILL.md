---
name: hd2-file-route-mod
description: |
  做「改盘上数据」的 Helldivers 2 mod：编辑 data/game/*.dl_bin 明文表（LDLD 容器），
  用 MurmurHash64A 反解校正字保住引擎内容哈希，重新 crypto_box_seal 封装，部署到游戏目录并实机验证/回滚。
  改的是磁盘数据文件，不碰进程内存、不需要 Lua/FFI/注入/DLL。
  当用户说「改战备冷却 / 使用次数 / 呼叫时间」「改爆炸半径 / 破片 / 外观」「改武器或实体表数值」
  「把改过的表装进游戏」「离线数据 mod」「dl_bin 改不动 / 改了崩 / 哈希不对」「LDLD」「校正字」
  「seal-key」时使用。也用于排查 0xC000000D 启动失败与 game.dll+0x1083a45 崩溃归因。
  关键词：Helldivers 2, dl_bin, LDLD, MurmurHash64A, content hash, file route, data table modding。
---

# HD2 改盘上数据的 mod（file route）

一份 `.dl_bin` 有**两层**封装，任何一步漏掉都白改：

```
① 容器层：epk(32) ‖ tag(16) ‖ ciphertext     明文 = ciphertext，文件 = 明文 + 48 B
② 内容层：引擎重算 MurmurHash64A(明文) 与 game.dll 里烘焙的期望值比对
          —— 改一个字节就失配 → 0xC000000D（封装再正确也没用）
```

⇒ 能写回的前提是：**改完之后，新明文的哈希仍然等于原明文的哈希**。
唯一手段是反解一个 8 字节对齐的**校正字**，把它写进一个**语义惰性**的位置（"宿主"）。

完整原理、实测数值与案例见 [FILE-ROUTE-WORKFLOW-26088801.md](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md)。
本技能是它的**可执行版**：只讲"按什么顺序跑什么命令、什么条件下必须停"。

---

## 0. 前置（缺一条就停，不要硬试）

| 需要 | 怎么确认 | 缺了怎么办 |
|---|---|---|
| `recipient.pk` / `recipient.sk` | 用户自备（**本仓库不提供，也不应该提供**） | 停。没有它既解不开也封不回去 |
| 游戏**已退出** | 部署前确认进程不在 | 让用户关游戏（表在启动时读入） |
| 知道目标 build 号 | `<游戏>/steamapps/appmanifest_553850.acf` 里的 `buildid` | 取到再谈偏移；偏移逐 build 失效 |
| Python 3.11+ | `python -V` | 停 |
| PyNaCl（仅封装/解封需要） | `python -c "import nacl"` | `pip install pynacl` |
| 工作目录 | 仓库根（命令都是 `python tools/...` 相对路径） | `cd <repo>` |

**永远先做基线缓存**（它同时给你"明文 + 同目录的 typelib"）：

```bash
python tools/build_cache.py --sk <recipient.sk> \
    --game "<游戏>" --appmanifest "<...>/appmanifest_553850.acf"
#  -> refs/dlbin/plaintext-<buildid>/   55 张表 + dl_library.dl_typelib
```

> ⚠ 缓存被污染过一次就很难发现：如果 `data/game` 里已经装着你的 mod，dump 出来的"原版"其实是
> 你的负载，之后所有"这张表变了没"的判断全错。**dump 前确认盘上是原版。**

---

## 1. 八步

### Step 1 · 取明文（先用 `build_cache.py` 建基线）+ 两个自检

```bash
python tools/dlbin_seal.py open-key --key <recipient.sk> \
    "<游戏>/data/game/<表>.dl_bin" --out <work>/dlbin/<表>.dl_bin
python tools/dlbin_seal.py blocks <work>/dlbin/<表>.dl_bin     # 组数/type/payload
python tools/murmur64.py   <work>/dlbin/<表>.dl_bin            # 明文内容哈希
```

**停的条件**：`blocks` 报 `not a plaintext container` ⇒ 解错了（错 key / 不是 dl_bin）；
哈希不等于本 build 的锚点 ⇒ **build 变了，偏移不可复用**，先读 [BUILDS.md](../../BUILDS.md) §3。

本 build（`26088801`）锚点，可直接比对：

| 表 | 明文 B | 锚点 Murmur64A |
|---|---:|---|
| `generated_stratagem_settings` | 82,384 | `04BBE33EF809862A` |
| `generated_explosion_settings` | 68,156 | `2ABCD21D2536373D` |
| `generated_projectile_settings` | 96,604 | `946A4FE5FAAAE076` |
| `generated_entities` | 47,259,396 | `8E49771B181FFAA1` |

### Step 2 · 定位字段（不许"看着像"就动手）

按强度递增，**只有最后一条能定案**：

1. `python tools/table_dictionary.py --sk <sk> --game "<游戏>" --names refs/dl-type-names.txt --md <work>/DICT.md`
   —— 给偏移/宽度，**不给语义**（类型库字符串表是空的）；
2. wiki 数据模块 / 本地库：`python tools/wiki_query.py --page "<名字>"` —— 给语义与数值；
3. 外部 SDK（[HD2Runtime by SkyeShade](https://github.com/SkyeShade/HD2Runtime)）—— 给字段名，
   **引用时必须显式署名**；
4. **先写下一个具体预测，再上机只改一个字段**。

好的预测长这样：`+0x54` 写 12.0 ⇒ 面板「呼叫时间」应是 `12.0 + 2.45 − 1.0 = 13.45`。
坏的证据长这样：「弹幕行的 `+0x3C` 全是 5 ⇒ 它是轮数」（实机否证，它是投放方式枚举）。

**停的条件**：找不到一个能自洽解释**整列分布**的候选，或候选所在区域没有 8 对齐空位
⇒ 先解决宿主问题（见 Step 3 的 tail），不要先改字节。

### Step 3 · 写入 + 保哈希

按表选工具，**不要手写 struct.pack 绕过门禁**：

| 表 | 工具 | 寻址 |
|---|---|---|
| 战备 `generated_stratagem_settings`（stride 400） | `tools/stratagem_tune.py` | 内部名（精确优先/否则子串）或 `+0` |
| 任意 `LDLD` 容器 | `tools/plain_edit.py` | **文件绝对偏移** |
| 爆炸 `generated_explosion_settings`（stride 152） | `tools/expl_set.py` | 爆炸 type + 行内偏移 |
| 弹丸整行搬运 | `tools/proj_copy_row.py` | type / 行号 |
| 实体 `generated_entities`（275 块） | `tools/entities_modeb.py` 只覆盖"可选弹种"两格；其余字段自写 | 绝对偏移 |

```bash
# 战备：一次封装可改多行（--edit 可重复；串两次会失效，因为哈希锚点是原始明文）
python tools/stratagem_tune.py --plain <work>/dlbin/generated_stratagem_settings.dl_bin \
    --edit "EAGLE. AIRSTRIKE::cooldown=4" \
    --edit "EAGLE. REARM::cooldown=5" \
    --out <work>/stratagem.new.plain.dl_bin

# 任意偏移（值必须带类型前缀）
python tools/plain_edit.py --plain <plain> --out <out.plain> --set 0x<偏移>=u32:<值>
```

战备字段（`build 26088801`，`+0` 之外都不许乱动）：

| 字段 | 偏移 | 类型 | 备注 |
|---|---|---|---|
| 条目 ID | `+0x00` | u32 | **主键**，`1..153` 连续；重复 = 崩 |
| 名称 locid | `+0x28/+0x2C/+0x30` | u32 | 改它就能借现有字符串改名/改描述 |
| 投放方式 | `+0x3C` | u32 | ⚠ **不是轮数**（Eagle 0 / 单发 1 / 武器 2 / 弹幕 5） |
| 使用次数 | `+0x50` | u32 | `0xFFFFFFFF` = 无限；**鹰式 = 每次回收次数** |
| 呼叫时间 | `+0x54` | f32 | 面板 = 基础值 + 交付延迟（ORBITAL +2.45 / BACKPACK +4.75 / EAGLE +4.10）− 升级 |
| 未知 | `+0x60` | f32 | ⚠ 空袭行为 0、`EAGLE. REARM` 为 15.0，语义未解 |
| 冷却 | `+0x68` | f32 | 面板 = 基础值 × 各升级相乘（已见 ×0.90 ×0.95）；REARM 行上 = **回收时间** |
| 面板格 | `+0x188` | u32 | 分类/格号 |
| 身份 | `+0/+40/+44/+48/+52/+56` | — | **不许动**（G7 会拦） |

**实体表（`generated_entities`）**：首 `u32` 不是组数（是块类型标签），`plain_edit.py` 会拒绝。
它的形状是 **275 个 `LDLD` 块**，每块前 4 B 是类型标签（块头共 28 B）。写法：

```
扫 "LDLD"（按 payload 跳，别按 4 字节步进）→ 记下每个块 at / payload_size
→ 改目标绝对偏移的字节
→ 取末块：payload_size += pad+8，文件末尾追加零字节
→ 校正字写到 word_at = 原长度 + pad（必须 %8==0）
→ 门禁：长度 / 差异集合 / 哈希复原 / 读回 / 块仍连续到新尾
```

### Step 4 · 读门禁（全 PASS 才继续）

| 门禁 | 它在防什么 | 失败说明 |
|---|---|---|
| G1 长度 | 重建容器写坏长度 | 你的 `pad + 8` 算错 |
| G2 差异 ⊆ 声明 ∪ 尺寸字段 ∪ 校正字 | **顺手改到别处**（最重要的一道） | 偏移算错、越界写 |
| G3 重算哈希 == 原值 | 保哈希失败 | 校正字位置不是 8 对齐，或改的是大小不匹配的字 |
| G4 声明字段读回 | 宽度/偏移错 | `f32` 写成 `u32` |
| G5 其余字节未动 | 重建丢字节 | 容器重排有 bug |
| G6 容器自洽 | 忘同步 `payload_size` | tail 宿主少改一处 |
| G7 身份字段未变 | 撞主键（三次崩溃的根因） | 你把 `+0`/locid 带进去了 |

**门禁全绿 ≠ 功能生效。** 它只证明"我按自己声明改了"，不证明"引擎读这个字段"。

### Step 5 · 重新封装

```bash
python tools/dlbin_seal.py seal-key --key <recipient.pk> <work>/x.plain --out <work>/x.dl_bin
```

判据：**封包 = 明文 + 48 B**。同一份明文封两次，文件哈希**必然不同**（新随机 epk/tag）——
比内容只比明文哈希。

### Step 6 · 往返校验（别省）

```bash
python tools/dlbin_seal.py open-key --key <recipient.sk> <work>/x.dl_bin --out <work>/rt.plain
cmp <work>/rt.plain <work>/x.plain     # 必须逐字节相同
```

### Step 7 · 部署（备份 → 替换 → 盘上回读）

```bash
cp "<游戏>/data/game/<表>.dl_bin" "<work>/backup/"          # 第一次装之前，之后永不覆盖
cp "<work>/x.dl_bin" "<游戏>/data/game/<表>.dl_bin"
python tools/dlbin_seal.py open-key --key <recipient.sk> \
    "<游戏>/data/game/<表>.dl_bin" --out <work>/readback.plain
python tools/murmur64.py <work>/readback.plain              # 必须仍等于锚点
```

并把四个字段记进账本（`backup_sha256` / `installed_sha256` / `installed_from` / `installed_at`）。
回滚 = 把备份 `cp` 回去 + 核 sha256。

### Step 8 · 实机验证 + 记账

| 字段类型 | 验法 | 关键 |
|---|---|---|
| 面板上有的数 | 进游戏看战备面板 | **面板 = 基础值 × 该玩家升级**，先换算 |
| 面板上没有的数（轮数/散布/间隔） | 进任务数或计时 | 同样吃升级（弹幕轮数有 `+1`） |
| 视觉 | 进任务开一炮 | 灰色方块 = 代码跑了但资源缺（免费探针） |

**说"已上机"必须同时给出三样**：① 账本 `installed_from` 指向本次产物 ② **从盘上文件解回来**的
字段值等于目标 ③ 进程存活/正常启动。缺一样只能说"已部署未验证"。

汇报里给：改了什么（表/行/字段/旧值→新值）、门禁结果、**预测值 vs 实测值**、
账本四项、回滚命令。**没测的写 ⚠，否掉的写 ✗ 并写清怎么否的。**

---

## 2. 坑（按踩到的次数排序）

| # | 症状 | 根因 | 修法 |
|---:|---|---|---|
| 1 | 启动即崩：`0xc0000005 @ game.dll+0x1083a45`，寿命 26–29 s | 校正字写进了**记录行行首**，把 `+0` 主键改成随机值 | 宿主只用 **tail**；行内宿主必须避开 `+0`/`+4` |
| 2 | 整行被抹成 158 个零字节 | `--set 0x979c=158` 的裸整数被当成"宽度 158 字节" | 值必须 `u32:158` / `f32:12.5` / `hex:…` |
| 3 | `--name "Orbital Laser"` 命中 0 行 | 表里是**内部名** `ORBITAL. LASER` | 用内部名；`EAGLE. AIRSTRIKE` 与 `... SMOKE` 要用精确名区分 |
| 4 | 改了"轮数"没反应 | `+0x3C` 是投放方式枚举 | 轮数在实体表 Bombardment `+0x18` |
| 5 | 改了但面板数不对 | 面板 = 基础值 × 玩家升级 | 先换算；不同玩家看到的数本来就不同 |
| 6 | 面板上看不到变化 | 该字段面板不显示 | 进任务计时；别拿"看不见"当"没生效" |
| 7 | 门禁 G4 拒写：整块 hex 与块内字段互相覆盖 | 一次 `--set` 里既写整块又写块内字段 | 先把字段改好、合成一个 hex 块，一次写入 |
| 8 | "已验证"结论后来被推翻 | 部署的不是那个变体（账本指向别的 probe） | 三样证据（账本/盘上回读/进程状态）缺一不可 |
| 9 | 更新被误报"改了一张表" | 明文缓存被自己的 mod 负载污染 | dump 前确认原版；换 build 重跑 `build_cache.py` |
| 10 | 加一行就崩 | `+0` 是主键，复制行沿用原 ID ⇒ 重复键 | 新行 `+0 = max+1`（现为 154） |
| 11 | 只换粒子字段，特效不出现 | 引擎要**整行一致**（克隆）且**包要已加载** | 整行克隆 + `+0xA8` 指向供体的包 |
| 12 | 灰块而不是特效 | 资源不在任何已加载的包里 | 改 `+0xA8`；灰块证明代码路径是通的 |
| 13 | 工具在 Windows 控制台打印时崩 | GBK 没有 `⚠`/`✗` | 已内置 `reconfigure(encoding="utf-8")`；自写脚本也要加 |
| 14 | `stratagem_tune.py` 报"找不到 typelib" | 它要求 `dl_library.dl_typelib` 与 `--plain` **同目录** | 用 `build_cache.py` 的输出目录 |
| 15 | 启动 `0xC000000D` | 封装对但**内容哈希**没还原 | 回 Step 3；不是封装问题 |

---

## 3. 不许做的事

- **不要**把校正字放进任何记录行的 `+0` / `+4`（主键）。三次崩溃都是这个。
- **不要**在没有 8 对齐宿主的表上硬改（先用 tail 自造，或放弃这张表）。
- **不要**改 `+0` 主键去"占用"别人用过的值；也不要指望加行能让新条目**显示**（成员资格在表外）。
- **不要**用封包文件的哈希判断内容是否一致（每次封装的 epk/tag 都不同）。
- **不要**在游戏运行时替换文件。
- **不要**把 `recipient.pk/sk`、明文表全集、实体库、mod 补丁写进任何要提交的东西里。
- **不要**在没有盘上回读的情况下宣称"已上机"。
- **不要**把"门禁全绿"当成"功能生效"。

---

## 4. 边界（提前知道就不用白试）

| 想做 | 能不能 | 说明 |
|---|---|---|
| 改数值（冷却/呼叫/次数/半径/破片/散布） | ✓ | 本文全篇 |
| 改名字/描述 | ✓ | 借**现有** locid；写自定义字符串要改 `.strings`（另一条路线） |
| 加行 / 删行 | ✓ | 必须给未占用的 `+0` |
| 让新增行**显示** | ✗ | 成员资格不在 55 张明文表里（与"未发布物品"同构） |
| 换爆炸外观 | ✓ | 三步链：克隆爆炸行 + 弹丸 `+0x90` + 战备 `+0xA8` |
| 改伤害行 | ⚠ | `DamageInfo` 76 B **零 padding**，需要别的宿主方案 |
| 换引擎行为 / 绕过反作弊 | ✗ | 不做，也不在数据文件的能力范围内 |

---

## 5. 参考

- [FILE-ROUTE-WORKFLOW-26088801.md](../../docs/cases/FILE-ROUTE-WORKFLOW-26088801.md) —— 原理 + 实测数值 + 案例（本文的完整版）
- [DLBIN-SEALED-BOX.md](../../docs/engine/DLBIN-SEALED-BOX.md) —— 密封盒模型
- [STRATAGEM-FIELDS-26088801.md](../../docs/tables/STRATAGEM-FIELDS-26088801.md) —— 战备字段与面板公式
- [EXPLOSION-VISUAL-26088801.md](../../docs/explosions/EXPLOSION-VISUAL-26088801.md) —— 视觉与跨包加载
- [TABLE-DICTIONARY-25988413.md](../../docs/tables/TABLE-DICTIONARY-25988413.md) —— 全表几何与字段树
- [BUILDS.md](../../BUILDS.md) —— 换 build 先做什么
