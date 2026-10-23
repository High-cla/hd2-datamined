# 改盘上数据的 mod：完整工作流（build `26088801`）

> **一句话**：`data/game/*.dl_bin` 是**密封盒 + 内容哈希闸门**两层封装。改字节本身不难，
> 难的是改完还要让 `MurmurHash64A(明文)` **回到原值** —— 本文把"取明文 → 定位字段 → 保哈希写入 →
> 门禁 → 重封 → 部署 → 实机验证 → 回滚"这整条链写成可复现的八步。
>
> 这条路**不碰进程内存**、不需要 Lua / FFI / DLL 注入：改的只是磁盘上的数据文件，引擎启动时自己读。
>
> **三态口径**：`✓` 已实机（有上机读数，且**账本 `installed_from` + 盘上回读值 + 进程状态**三项齐全）·
> `✗` 否证（试过，不通，写清怎么否的）· `⚠` 未验证（有推理或离线证据，没上机）。**没有第四种。**
>
> 文件名带 build 号，是因为文中每个**偏移与实测数值**只对 `26088801` 成立；**流程本身跨 build 有效**。
> 换 build 先跑 [BUILDS.md](../../BUILDS.md) §3 的三步，再决定旧偏移能不能复用。

---

## 0. 这份文档不包含什么

| 不含 | 原因 |
|---|---|
| 任何密钥材料（`recipient.pk` / `recipient.sk`） | 私钥泄露 = 任何人都能伪造通过校验的数据文件。**需要使用者自备**，本仓库不提供 |
| 游戏资产、mod 补丁二进制、47 MB 实体库、全量 dump | 体积 / 版权 / 可再生成 |
| 解锁付费内容、绕过反作弊、与他人联机用的改动 | 不做 |

---

## 1. 一页速查

| 步 | 动作 | 命令 | 硬判据（不过就停） |
|---:|---|---|---|
| 1 | 建基线 + 取明文 | `python tools/build_cache.py --sk <sk> --game "<游戏>"` | 明文目录里有 `dl_library.dl_typelib`；`blocks` 能解析；`murmur64.py` 等于锚点值 |
| 2 | 定位字段 | `table_dictionary.py` + wiki/SDK 交叉 + 跨行统计 | 有**可证伪预测**（不是"看起来像"） |
| 3 | 写入 + 保哈希 | `stratagem_tune.py` / `plain_edit.py`（实体表另说） | 门禁全 PASS |
| 4 | 复核门禁 | 看工具输出 G1–G7 | **7/7 PASS**，diff 字节数 = 预期 |
| 5 | 重新封装 | `dlbin_seal.py seal-key --key <pk>` | 封包 = 明文 + 48 B |
| 6 | 往返校验 | `open-key` 解回 + `cmp` | 解回**逐字节相同** |
| 7 | 部署 | 备份 → 替换 → **盘上回读** | 回读值 = 目标值，哈希 = 锚点 |
| 8 | 实机验证 + 记账 | 进游戏看 / 进任务计时 | 先算预测值，再看读数；账本留档 |

> 全链只依赖 Python 3.11+ 标准库 + **PyNaCl**（只有 `dlbin_seal.py` 的 key 子命令需要）。

---

## 2. 四个必须先理解的事实

### 2.1 密封盒：明文 = 密文 − 48 字节

```
磁盘文件 = epk(32) ‖ tag(16) ‖ ciphertext        总长 = 明文 + 48
ciphertext = plaintext XOR keystream[32:]        （libsodium crypto_box_seal 形态）
```

| 事实 | 状态 | 后果 |
|---|---|---|
| 每个 `generated_*.dl_bin` 都比自己的明文长 **48 B** | ✓ 实测（9 个文件逐个吻合） | 长度可以直接当自检 |
| 引擎用 `crypto_box_seal`（X25519 + XSalsa20 + Poly1305） | ✓ 实测（exe 里四个相关串相邻） | 打开时会验 tag |
| **封装只需要公钥** `recipient.pk`，ephemeral 可以自己随机 | ✓ 实测 | 长度**没有上限**，tag 自己算 |
| 每次封装的 `epk` / `tag` 都不同 | ✓ 实测 | **不能用封包文件的哈希比内容**；要比就比明文 |

⇒ 写回的门槛从来不是"能不能封"，而是下一节。

### 2.2 内容哈希闸门：改一个字节就失配

引擎在加载时重算 **MurmurHash64A(明文)**，与 `game.dll` 里**烘焙的期望值**比对；
封装完全正确但内容对不上 → `0xC000000D`（`STATUS_INVALID_PARAMETER`）。

```
算法：MurmurHash64A，seed = 0xDEADBEEFABAD1DEA，乘数 0xC6A4A7935BD1E995，shift 47
```

**这不是"能不能改"的问题，是"改完哈希必须等于原值"的约束**：期望值是原版明文的哈希，
所以我们只能让**新明文的哈希 == 旧明文的哈希**，不能"重算一个新哈希写进去"。

### 2.3 解法：反解一个 8 字节**校正字**

哈希是逐 8 字节块迭代的，所以给定目标哈希，可以**代数反解**出某一个 8 字节对齐字的取值
（`murmur64.padding_word_for_hash(data, word_at, wanted)`，纯计算，不用爆破）。

**两个硬约束**：

1. `word_at % 8 == 0` —— 校正字必须落在**8 字节对齐**的字上（哈希按 8 B 一块吃）；
2. 那个字所在的位置必须**语义惰性** —— 它会被写成一个"随机数"，任何读它的代码都会看到垃圾。

第 2 条是这条路唯一的真边界：**语义空位在哪，这条路就能走到哪。**

### 2.4 宿主的选择顺序（这是用三次崩溃换来的）

| 宿主 | 做法 | 状态 |
|---|---|---|
| **tail（默认）** | 最后一组 `payload_size` 字段**加 8**（该字段在块头 `+12`），并在文件末尾追加 8 字节零区当宿主 | ✓ 实机两次（战备表、实体表） |
| 块头保留区（L1） | `LDLD` 头 `+16` 的 8 B（`wide`+`extra`），要求绝对偏移 8 对齐 | ⚠ 语义明确，但有"`wide` 必须仍是 1"的约束，需受约束反解 |
| 行内**非主键**空位 | 借某一行内部的 8 对齐空字（例：爆炸表用无主行 `+0x34`） | ⚠ 可用，但必须先证明那个字**没人读**；爆炸表 `+0x34` 已实机通过 |
| 行首 8 字节 | 借一条"看起来没用"的记录的**行首** | ✗ **已崩三次**，见下 |

**三次崩溃（`0xc0000005 @ game.dll+0x1083a45`，会话寿命 26–29 秒，签名逐字相同）**：

| 变体 | 长度 | 行数 | 校正字落在哪 | 结果 |
|---|---|---|---|---|
| 复制一行 `(NOT USED)` | +400 | 11→12 | `(NOT USED)` 行开头 | ✗ 崩 |
| 只把 380mm 的 `+0` 改成别人占用过的值 | 不变 | 不变 | 同上 | ✗ 崩（同签名）|
| 等长改冷却 240→60 | 不变 | 不变 | 同上 | ✗ 崩（同签名）|
| 只加 8 字节尾巴 | +8 | 不变 | 追加的尾巴 | ✓ 通过 |

> **根因**：`stratagem_tune.py` 的 `--host-mode row` 把 `(NOT USED)` 行的行首当宿主，
> 而那 8 字节正是该行的 **`+0` 条目 ID 与 `+4` 名字 ID**。写进去 = 把主键改成随机值。
>
> **教训（一条值得背下来的话）**：**"这一行面板不渲染" ≠ "引擎不读它的字段"。**
> 渲染与"读表建索引"是两条独立路径。看不见 ≠ 无副作用。

⇒ 因此：`stratagem_tune.py` 的默认宿主是 **tail**（`--host-mode row` 保留但标为"实机已验证会崩"）；
`expl_set.py` / `proj_copy_row.py` 走的是**行内非主键空位**，落点必须由 `--host-type` + `--host-offset`
显式指定 —— **这两个参数就是"我确认过 8 字节没人读"的声明**，不要随便填。

---

## 3. 容器几何：`LDLD`

### 3.1 三级头

```
文件 = u32 group_count(4) │ 组 × { "LDLD" + 组头 + payload }
组    = "LDLD"(4) ‖ u32 version ‖ u32 type_id ‖ u32 payload_size ‖ u32 wide ‖ u32 extra   ← 24 B
payload（数组型）= 描述符 16 B（首 u64 固定 = 0x10 当标记，第二个 u64 = count）‖ 行 × stride ‖ 尾部变长块（可能不存在）
```

推导：单组表的**行区绝对偏移 = 4（组数）+ 24（LDLD 头）+ 16（数组描述符）= 44**。
多组表则每组各自从 **`payload + 16`** 起。

> ⚠ 一处**措辞**要小心：早期文档写"爆炸行基址 = `payload + 44`"，那个 44 其实是**文件绝对偏移**。
> `payload` 相对是 **+16**。实测判据：从 `payload+16` 起每 152 B 取一个 u32，得到 **1..424 的全排列**；
> 从 `payload+44` 起取则全是 0。写工具时用哪个基准，差了 28 B 就是改错字段。

### 3.2 行步长从类型库来（不要猜）

```bash
python tools/table_dictionary.py --sk <recipient.sk> --game "<游戏>" \
    --names refs/dl-type-names.txt --md <work>/DICT.md --json <work>/dict.json
```

`Dictionary.element_of(type_id) → (element_type_id, stride)`：容器类型若只包一个成员、且该成员记录更大，
就返回成员类型与它的记录大小。行数来自描述符里的 `count`，**不要**用 `payload // stride` 反推
（有尾块的表会算错）。

### 3.3 本 build 的已知几何（`26088801`，均可自己复算）

| 表 | 明文 B | 组 | 行 | stride | 行区起点 | 尾块 | 明文 Murmur64A（锚点） |
|---|---:|---:|---:|---:|---|---:|---|
| `generated_stratagem_settings` | 82,384 | 12 | 153 | 400 | 每组 `payload+16` | 字符串块 | `04BBE33EF809862A` |
| `generated_explosion_settings` | 68,156 | 1 | 424 | 152 | 文件偏移 **44** | 3,664 B（震屏表） | `2ABCD21D2536373D` |
| `generated_projectile_settings` | 96,604 | 1 | 355 | 272 | 文件偏移 **44** | 0 | `946A4FE5FAAAE076` |
| `generated_entities` | 47,259,396 | — | — | 按块 | 每块 `payload` | — | `8E49771B181FFAA1` |

**锚点哈希的用法**：拿到明文先算一次，等于上表 ⇒ 你的 `build` 与这份文档一致，偏移可以直接用；
不等于 ⇒ 停，先跑 [BUILDS.md](../../BUILDS.md) §3。

```bash
python tools/murmur64.py <work>/dlbin/generated_stratagem_settings.dl_bin
```

### 3.4 `generated_entities` 是特例

它不是"`u32` 组数 + 连续 `LDLD` 块"：首个 `u32` 是**块类型标签**，不是计数。
实际形状是 **275 个 `LDLD` 块**，每块前面 4 B 是类型标签（所以块头实际 28 B）：

```
u32 type_tag │ "LDLD" ‖ ver ‖ type_id ‖ payload ‖ wide ‖ extra ‖ payload
```

⇒ **`plain_edit.py` 用不了这张表**（它按首 `u32` 当组数解析，会直接拒绝）。
实体表要用"扫 `LDLD` → 按 payload 跳"的写法（算法见 Step 3 末的「实体表」一段，
门禁对齐 Step 4 表里的 `ent_set` 口径）。

---

## 4. 八步工作流

### Step 1 · 建基线 + 取明文（每次换 build 必做）

```bash
python tools/build_cache.py --sk <recipient.sk> \
    --game "<游戏>" --appmanifest "<...>/appmanifest_553850.acf"
#   -> refs/dlbin/plaintext-<buildid>/   （55 张表 + dl_library.dl_typelib 放同一目录）
```

> **为什么必须"干净"**：只要有一次 dump 发生在**我们的 mod 已写进 `data/game` 之后**，
> 缓存里就会混进改过的表 —— 之后所有"这张表变了没"的判断全错，而且错得很有说服力
> （真实发生过：把 4,992 B 的 mod 负载存成了 4,016 B 的原版，导致下一次更新被误报"改了一张表"）。
> 详见 [BUILDS.md](../../BUILDS.md) §6。

只改一张表时也可以单张解，然后跑两个自检：

```bash
python tools/dlbin_seal.py open-key --key <recipient.sk> \
    "<游戏>/data/game/generated_stratagem_settings.dl_bin" --out <work>/dlbin/generated_stratagem_settings.dl_bin

python tools/dlbin_seal.py blocks <work>/dlbin/generated_stratagem_settings.dl_bin   # 12 组、末组 6,420 B
python tools/murmur64.py   <work>/dlbin/generated_stratagem_settings.dl_bin          # 04BBE33EF809862A
```

> ⚠ `stratagem_tune.py` 要求 `dl_library.dl_typelib` 与 `--plain` **在同一目录**，否则直接退出
> （报"找不到 typelib"）。`build_cache.py` 的输出目录天然满足；手工逐张解封时最容易漏这一步。

### Step 2 · 定位字段（四种证据，强度差三个量级）

| 证据源 | 能给什么 | 不能给什么 |
|---|---|---|
| `table_dictionary.py --md` 的字段树 | 偏移、宽度、类型嵌套 | **语义**（类型库被剥了字符串表，名字是空的） |
| wiki 数据模块 / 本地 SQLite（`tools/wiki_*.py`） | 字段语义 + 数值 | 不保证与本 build 同步 |
| 外部 SDK（[HD2Runtime by SkyeShade](https://github.com/SkyeShade/HD2Runtime)、SSEO） | 现成字段名与用法 | 版本可能落后；引用需显式署名 |
| **跨行统计 + 单变量实机** | **唯一能定案的东西** | 需要一次上机 |

**定案仪式（缺一不可）**：

1. 跨行统计找一个**只与你的假设自洽**的分布（例：全部弹幕 `+0x3C` 都是 5）；
2. **写下一个具体预测**（"改成 12.0，面板应当显示 `12.0 + 2.45 − 1.0 = 13.45`"）；
3. 只改**一个**字段，上机读**另一个**可读数；
4. 命中 ⇒ 字段语义 + 加成模型同时坐实；不中 ⇒ 假设错，**不是"没生效"**。

> 反面教材：（a）"弹幕行 `+0x3C` 全是 5" ⇒ 猜它是轮数，实机否证（它是**投放方式枚举**）；
> （b）只看单个样本就断言 `+0x54` 不是呼叫时间，后来全表 × wiki 的相关性检验证明**它就是**
> （面板 = 基础值 + 交付延迟）。

### Step 3 · 写入并保哈希（挑工具）

| 场景 | 工具 | 寻址方式 | 门禁 |
|---|---|---|---|
| 战备表（`StratagemSettings`，400 B 行） | `tools/stratagem_tune.py` | **内部名**（精确优先 / 否则子串）或 `+0` type | G1–G7 |
| 任意 `LDLD` 容器、任意偏移 | `tools/plain_edit.py` | **文件绝对偏移** | G1–G6 |
| 爆炸表（`ExplosionSettings`，152 B 行） | `tools/expl_set.py` | 爆炸 type（行 `+0`）+ 行内偏移 | G1–G6 |
| 弹丸整行搬运 | `tools/proj_copy_row.py` | 行号 / type | G1–G5 |
| `generated_entities`（275 块） | 需按 §3.4 自写"扫块 + tail 宿主"写入（`entities_modeb.py` 只覆盖可选弹种两格） | 绝对偏移 | 建议同 G1–G5 |

**战备表：一次封装改多行**（`--edit` 可重复，哈希锚点仍是**原始明文**，串两次会失效）：

```bash
python tools/stratagem_tune.py \
    --plain <work>/dlbin/generated_stratagem_settings.dl_bin \
    --edit "EAGLE. AIRSTRIKE::cooldown=4" \
    --edit "EAGLE. REARM::cooldown=5" \
    --out   <work>/stratagem.new.plain.dl_bin
```

**任意偏移**（值必须写成 `类型:值`，见 §8 第 2 条坑）：

```bash
python tools/plain_edit.py --plain <work>/dlbin/generated_explosion_settings.dl_bin \
    --out <work>/expl.new.plain.dl_bin --set 0x0000AC04=f32:12.5   # 偏移换成你自己的
```

### Step 4 · 读门禁（每一道在防一件具体的事）

| 门禁 | 防的是什么 | `plain_edit` | `stratagem_tune` | `ent_set` 口径 |
|---|---|:--:|:--:|:--:|
| G1 长度 = 原长 + 对齐 + 8 | 重建容器时写坏长度 | ✓ | ✓ | ✓ |
| G2 差异 ⊆ 声明字段 ∪ 尺寸字段 ∪ 校正字 | **顺手改到别处**（最有价值的一道） | ✓ | ✓ | ✓ |
| G3 重算哈希 == 原始哈希 | 保哈希失败 | ✓ | ✓ | ✓ |
| G4 声明字段读回 == 目标值 | 偏移算错、宽度写错 | ✓ | ✓ | ✓ |
| G5 其余字节 / 其它记录一字节未动 | 重建时丢字节（容器重排 bug） | ✓ | ✓ | （块连续到新尾） |
| G6 容器重新解析自洽、无尾部残留 | 忘记同步 `payload_size` | ✓ | （行内其余字段未变） | ✓ |
| G7 身份字段未变（`+0` / `+40..+56`） | **撞主键 / 改掉条目身份** | — | ✓ | — |

**门禁不是形式**：它只能证明"我按自己声明的改了"，不能证明"这个字段会被引擎读"。
后者只能靠 Step 8。**门禁全绿 ≠ 功能生效**（项目里真出过"全绿而效果为零"的事故）。

### Step 5 · 重新封装

```bash
python tools/dlbin_seal.py seal-key --key <recipient.pk> \
    <work>/stratagem.new.plain.dl_bin --out <work>/stratagem.new.dl_bin
```

判据：**封包字节数 = 明文 + 48**。`seal-key` 用**全新随机 ephemeral**，所以同一份明文封两次
得到两个不同的文件 —— 这是正常的，**不要**拿封包哈希去比对内容。

### Step 6 · 往返校验（别省这一步）

```bash
python tools/dlbin_seal.py open-key --key <recipient.sk> \
    <work>/stratagem.new.dl_bin --out <work>/roundtrip.plain
cmp <work>/roundtrip.plain <work>/stratagem.new.plain.dl_bin && echo "往返一致"
```

### Step 7 · 部署（备份 → 替换 → **盘上回读**）

> **先关游戏。** 表在启动时读入；且运行中替换文件可能被占用或读到半份。

```bash
# ① 备份（第一次装之前做一次，之后永不覆盖）
cp "<游戏>/data/game/generated_stratagem_settings.dl_bin" "<work>/backup/"
sha256sum "<work>/backup/generated_stratagem_settings.dl_bin"

# ② 替换
cp "<work>/stratagem.new.dl_bin" "<游戏>/data/game/generated_stratagem_settings.dl_bin"

# ③ ★ 盘上回读：从**装进去的那份**解回来读字段，不要从自己的产物里读
python tools/dlbin_seal.py open-key --key <recipient.sk> \
    "<游戏>/data/game/generated_stratagem_settings.dl_bin" --out <work>/readback.plain
python tools/murmur64.py <work>/readback.plain        # 必须仍等于锚点哈希
```

**账本**（推荐用一个 JSON 记，字段就这四个）：

```json
{ "generated_stratagem_settings.dl_bin": {
    "backup_sha256":    "<装之前那份的 sha256>",
    "installed_sha256": "<装进去那份的 sha256>",
    "installed_from":   "<产物文件名>",
    "installed_at":     "2026-10-23T15:06:46" } }
```

回滚只需 `cp "<work>/backup/<名字>" "<游戏>/data/game/<名字>"`，再核一次 sha256。

> `plain_edit.py` 结尾会提示 `tools/dlbin_deploy.py` —— 那是私有工作区里的参考实现（含账本与原子替换），
> **本仓库不含**。上面三步就是它的最小等价物；想要自动化，按这四条字段自己包一层即可。

### Step 8 · 实机验证（先算预测，再看读数）

| 字段类型 | 怎么验 | 注意 |
|---|---|---|
| 面板上**有**的数（官方数值：冷却 / 呼叫时间 / 使用次数 / 名称 / 描述） | 进游戏看战备面板 | **面板 = 基础值 × 该玩家升级**，先换算 |
| 面板上**没有**的数（轮数 / 散布 / 弹间隔 / 后坐） | **只能进任务里计时或数** | 同样吃升级（例：弹幕轮数有 `+1` 升级） |
| 纯视觉（特效 / 颜色） | 进任务开一炮 | 灰色方块 = 代码路径跑了但资源缺（免费探针） |

**这一步的产出不是"变了"，而是"等于我算的那个数"。** 只写"变了"等于只证明了字段被读，
没证明你理解它。冷却是 `× 0.90 × 0.95`，呼叫时间是 `+ 交付延迟 − 升级`，轮数是 `+ 升级` ——
换算错了会把"生效"误判成"没生效"。

---

## 5. 案例：一次封装同时改两行（`EAGLE. AIRSTRIKE` + `EAGLE. REARM`）

### 5.1 为什么这两行是分开的两条记录

`EAGLE. REARM` **不是**写在 8 条鹰式空袭行里的字段，它是战备表里**独立的一行**：

| 条目 | 位置 | `+0` type | `+0x50` uses | `+0x54` callin | `+0x60` ⚠未知 | `+0x68` cooldown |
|---|---|---:|---:|---:|---:|---:|
| `EAGLE. AIRSTRIKE` | 组2 行3（行首 `0x25A0`） | `0x12` | 2 | 0.0 | 0.0 | **15.0** |
| `EAGLE. REARM` | 组2 行8（行首 `0x2D70`） | `0x33`(51) | `0xFFFFFFFF` | 0.0 | 15.0 | **150.0** |

`EAGLE. REARM` 那一行的 `+0x68 = 150.0` 与 wiki 的"鹰式回收 150 s / Pit Crew −20% = 120 s /
Advanced Crew −10% = 108 s"同构（`150×0.8` 与 `150×0.8×0.9`），与我们已验证的"冷却升级相乘"模型一致。
⇒ 判定 `+0x68` 在 REARM 行上承载**回收时间**（同一字段、两种语义，随行的用途而变）。

> 命名来源：[HD2Runtime by SkyeShade](https://github.com/SkyeShade/HD2Runtime) 把这两个语义分别叫
> `hd2.fields.eagle.uses_per_rearm` 与 `eagle.rearm_time`，其 LICENSE 要求引用时显式署名。
> 本节的数值与实测是本仓库自己的。

### 5.2 一次写入、一次封装、7 门禁全过

```bash
python tools/stratagem_tune.py --plain <work>/dlbin/generated_stratagem_settings.dl_bin \
    --edit "EAGLE. AIRSTRIKE::cooldown=4" --edit "EAGLE. REARM::cooldown=5" \
    --out <work>/stratagem_eagle_cd4_rearm5.plain.dl_bin
```

```
明文 82,384 B  组 12  行 153
目标：组2 行3 type=0x12 'EAGLE. AIRSTRIKE'
目标：组2 行8 type=0x33 'EAGLE. REARM'
宿主：最后一组 payload 末尾追加 8 字节零区 @ 82384（不碰任何记录）
原始哈希 0x04BBE33EF809862A
  EAGLE. AIRSTRIKE  cooldown +104: 15.0 -> 4.0
  EAGLE. REARM  cooldown +104: 150.0 -> 5.0
  PASS  G1 长度  82,384 -> 82,392
  PASS  G2 差异 ⊆ 目标行 ∪ 校正字 (+尺寸字段)  diff=5  目标行 2
  PASS  G3 重算哈希 == 原始哈希  0x04BBE33EF809862A
  PASS  G4 目标字段读回  [('EAGLE. AIRSTRIKE', 'cooldown', 4.0), ('EAGLE. REARM', 'cooldown', 5.0)]
  PASS  G5 其它记录一字节未动  越界改动 []
  PASS  G6 目标行其余字段未变  越界改动的偏移 []
  PASS  G7 身份字段未变  offsets=(0, 40, 44, 48, 52, 56)
```

**整份明文只差 5 个字节**（这是"改得干净"最好的证据）：

| 文件偏移 | 属于 | 旧 | 新 | 说明 |
|---|---|---|---|---|
| `0x260A` `0x260B` | `EAGLE. AIRSTRIKE +0x68` 的**高两字节** | `70 41` | `80 40` | f32 `15.0 → 4.0`（低两字节 `00 00` 没变）|
| `0x2DDA` `0x2DDB` | `EAGLE. REARM +0x68` 的高两字节 | `16 43` | `A0 40` | f32 `150.0 → 5.0` |
| `0x128B0` | 末组 `payload_size` 的低字节 | `14`(=6,420) | `1C`(=6,428) | tail 宿主 +8 |
| `0x14190`–`0x14197` | 追加的 8 字节 | — | `5392a9e4ee8d692e` | **校正字**（`0x14190 % 8 == 0`）|

### 5.3 实机结果

| 观察项 | 改前 | 改后 | 判读 |
|---|---:|---:|---|
| 面板「冷却时间」 | 7 秒 | **2 秒** | ✓ `+0x68` 是运行时活字段 |
| 面板「使用次数」 | — | 3 | = vanilla 2 + Expanded Weapons Bay +1（未改动，符合预期）|
| 面板「呼叫时间」 | — | 4.10 秒 | = `+0x54`(0) + 鹰式交付延迟 4.10（未改动，符合预期）|
| 任务内回收 | 150 秒 | **3 秒多** | ✓ `+0x68` 在 REARM 行上就是回收时间 |
| 进程 | — | 正常进游戏、面板可读 | 进程存活（能读到面板即已跑完启动）|

**证据三项**（这是能打 `✓` 的前提，缺一项只能写"已部署未验证"）：

1. 账本 `installed_from = …/stratagem_eagle_cd4_rearm5.dl_bin`，`installed_at = 2026-10-23T15:06:46`；
2. 盘上回读：解回来 `+0x68` = `4.0` / `5.0`，明文哈希仍 `0x04BBE33EF809862A`；
3. 进程状态：正常启动、面板可读、无新崩溃签名。

> 本文编写时另做了一次**离线复跑**：同一条命令产出的明文与已部署产物**逐字节相同**
> （82,392 B、哈希 `0x04BBE33EF809862A`、封包 82,440 B、解回一致）。

### 5.4 ⚠ 两个还没答的问题（别把它们当结论）

| 问题 | 现状 | 怎么测 |
|---|---|---|
| 面板「冷却」在**鹰式**上是怎么算的？ | 观察到的两点是 `15→7`、`4→2`，与"`floor(基础值/2)`"两个点都吻合；但分母 2 没有来源，也可能只是巧合 | 把 `+0x68` 设成 **9**：`floor(9/2)=4` vs 标准模型 `9×0.855=7.7`，一次就能分开 |
| 回收时间的升级系数是 `×0.8` 还是 `×0.8×0.9`？ | `150→5` 后实测"3 秒多"；`5×0.8=4` 与 `5×0.8×0.9=3.6` 都落在读数范围内，**没分开** | 把 `+0x68` 设成 **10**：`8` 还是 `7.2`，一次分开 |

---

## 6. 案例：跨表联动（视觉要改三个文件）

换一个爆炸的**外观**，不是改一行就能成的 —— 三个文件各改一处，链起来才成立：

```
① 爆炸表：把供体爆炸的整行 [4, 152) 克隆到一个"无主行"（保留目标自己的 +0）
② 弹丸表：命中爆炸 +0x90 = 克隆行自己的 type
③ 战备表：+0xA8 = 供体资源所在的**包**（这一步才让引擎去加载那个包）
```

> 基数提醒：本文用十六进制（`+0x90`），[EXPLOSION-VISUAL](../explosions/EXPLOSION-VISUAL-26088801.md)
> 与 SSEO 用十进制（`+144` = `0x90`，`+156` = `0x9C`）。**同一个字段，两种写法**，换算时别错。

| 只做哪几步 | 结果 |
|---|---|
| 只改 ① 的 `+0x38`（粒子 id） | **什么都没有**（四次反例） |
| ①②（克隆） | **灰色半透明方块** —— 代码路径跑了，但资源不在任何已加载的包里 |
| ①②③（`+0xA8` 指向火粒子包） | **火球** ✓ |
| ①②③ 再把 `+0xA8` 回滚 | 火球消失（归因对照） |

⇒ 视觉的判据不是"资源在不在磁盘上"（同一 `file_id` 平均 5 份副本），而是
**`+0xA8` 声明的那个包有没有被加载**。详见 [EXPLOSION-VISUAL](../explosions/EXPLOSION-VISUAL-26088801.md)。

**工程含义**：一次改动跨 N 张表 ⇒ **N 次封装、N 次部署、N 条账本**，而且**回滚要一起回滚**。
只回滚其中一张，会留下"引用了不存在的行"的半套数据。

---

## 7. 三态总表（这条路现在到哪了）

| 能力 | 状态 | 证据 |
|---|---|---|
| 解封任意 `data/game/*.dl_bin` | ✓ | 56/56 解出，`blocks` 逐组解析 |
| 封装任意长度 | ✓ | 82,432 B 往返；封包 = 明文 + 48 |
| 内容哈希**可反解复原** | ✓ | 本 build 四张表的锚点值都能解回去 |
| 等长改数值（冷却 / 呼叫 / 次数） | ✓ | §5；面板读数命中预测 |
| 变长（+8 尾巴当宿主） | ✓ | `struct_pad8`：只有一个 8 字节尾巴，别的不动 |
| 加一行 / 删一行 | ✓ | 必须给**未占用**的 `+0`；取 `max+1`（`1..154` 实测无重复） |
| 加行后**新增可见条目** | ✗ | 面板仍只有一条 —— 成员资格在表外（§9） |
| 改名字 / 改描述（借**现有** locid） | ✓ | `+0x28` 大写名 / `+0x2C` 显示名 / `+0x30` 描述；实测同改前两者 ⇒ 面板换名、描述不动 |
| 写**自定义**字符串 | ✗ | 要改 `.strings` 语料（bundle 资源，另一条路线） |
| 改弹幕轮数 / 散布 / 每轮弹数 | ✓ | 都在**实体表**的 Bombardment 组件，不在战备表（§3.3 的提示） |
| 改爆炸外观 | ✓ | 三步链（§6） |
| 改 `+0` 主键 | ✗ | 重复 = 崩；换值 = 条目从面板消失（⚠ 后一半只推断未测） |
| 伤害/穿甲 | ⚠ | `DamageInfo` 76 B **零 padding**，需要别的宿主方案 |
| 20 张"零空位"表（`planet_override` / `planet_color_set` / `weather_color_set` 等） | ⚠ | 无内建空位；"尾部自造 padding +8"已在战备表验证，但这些表**逐表未验证** |

---

## 8. 坑清单（每条都真花过时间）

| # | 症状 | 根因 | 修法 |
|---:|---|---|---|
| 1 | 改完启动即崩，`0xc0000005 @ game.dll+0x1083a45`，寿命 26–29 秒 | **校正字写进了记录行**，把 `+0` 主键改成随机值 | 宿主只用 tail；行内宿主必须避开 `+0`/`+4` |
| 2 | 整行被抹成 158 个零字节 | `--set 0x979c=158` 这种**裸整数**被当成"宽度 158 字节" | 值必须写成 `u32:158` / `f32:12.5` / `hex:…`；`plain_edit.py` 已强制带冒号 |
| 3 | `--name "Orbital Laser"` 命中 0 行 | 表里存的是**内部名**（`ORBITAL. LASER`），不是面板显示名 | 用内部名；精确名优先、否则子串 |
| 4 | 改了"轮数"却不生效 | `+0x3C` 是**投放方式枚举**，不是轮数；轮数在实体表 Bombardment `+0x18` | 换表改；先看 [STRATAGEM-FIELDS](../tables/STRATAGEM-FIELDS-26088801.md) |
| 5 | 明明改了，面板数不对 | 面板 = **基础值 × 该玩家升级**（冷却 `×0.90×0.95`） | 先换算再判；不同玩家看到的数本来不同 |
| 6 | 面板上看不到变化 | 该字段**面板不显示**（轮数 / 散布 / 间隔） | 进任务数/计时；同样吃升级（轮数 `+1`） |
| 7 | 一次 `--set` 里既有整块 `hex:` 又有块内字段 ⇒ 门禁拒写 | 两块**互相覆盖** | 先把字段改好，合成一个 hex 块，一次写入 |
| 8 | "已验证生效"结论被推翻 | 部署的**不是**那个变体（账本指向另一个 probe） | 报"已上机"必须给：账本 `installed_from` + **盘上回读** + 进程状态 |
| 9 | 游戏更新被误报"改了一张表" | 明文缓存被**自己的 mod 负载**污染 | dump 前确认 `data/game` 是原版；每次换 build 重跑 `build_cache.py` |
| 10 | 加一行就崩 | `+0` 是**主键**，复制行沿用了原 ID ⇒ 重复键 | 新行 `+0` 取 `max+1`（现在的 `1..154` 已无空洞） |
| 11 | 只改粒子 id，特效不出现 | 引擎要**整行一致**（克隆），且**包要加载** | 整行克隆 + `+0xA8` 指包（§6）|
| 12 | 换了粒子却看到**灰色方块** | 代码路径跑了，但资源不在任何已加载的包 | 这是**免费探针**：灰块 = 缺包，不是"没生效" |
| 13 | 工具在 Windows 控制台打印时崩 | 默认 GBK 编码没有 `⚠`/`✗` | 工具里 `sys.stdout.reconfigure(encoding="utf-8")`；已内置 |
| 14 | `stratagem_tune.py` 直接退出：找不到 typelib | 它要求 `dl_library.dl_typelib` 与 `--plain` **同目录** | 用 `build_cache.py` 的输出目录，或把 typelib 一起解到同目录 |
| 15 | 同一份明文封两次，文件哈希不一样 | `seal-key` 每次用**新随机 ephemeral**（epk/tag 都变） | 比内容用**明文哈希**，不要比封包哈希 |
| 16 | 部署后游戏报 `0xC000000D` | 封装正确但**内容哈希**没还原 | 回 Step 3 保哈希；不是封装问题 |

---

## 9. 能力边界：能改什么、改不到什么

| 层 | 内容 | 载体 | 状态 |
|---|---|---|---|
| **层 2 · 定义** | 这条**叫什么、什么数值** | `generated_stratagem_settings`（以及爆炸/弹丸/实体表） | ✓ 可改（本文全篇） |
| **层 1 · 成员资格** | 面板上**有哪几条** | **不在 55 张明文表里** | ✗ 改不到（加行不显示；与"未发布物品"同构：由后端目录 / 组件挂接决定） |
| 字符串 | 任意自定义文本 | `.strings` 语料（bundle 资源） | ✗ 需另一条路线（`srkit` 那一侧） |
| 引用 | 让 A 指向 B | 表内字段（`+0x98` 实体哈希数组、`+0x90/+0x9C` 爆炸 type、`+0xA8` 包） | ✓ 可改，但**引用目标必须已存在**，否则是悬空引用 |

**一张表的可改性 = 它有没有一个可以随便写 8 字节的地方。** 判定方法：
跑一遍宿主扫描（找 8 对齐、语义为空的字），或直接用 **tail** 在末尾自造一个 ——
后者已在战备表上实机验证（+8 B 被接受），但对"零空位表"**逐表未验证** ⚠。

---

## 10. 附录

### A. 命令速查

```bash
# 基线
python tools/build_cache.py --sk <sk> --game "<游戏>"

# 自检
python tools/murmur64.py <plain>                     # 明文内容哈希（锚点比对）
python tools/dlbin_seal.py blocks <plain>            # 组/type/payload 一览
python tools/dlbin_seal.py inspect <sealed>          # 48 B 头（epk/tag）

# 写入（保哈希 + 门禁）
python tools/stratagem_tune.py --plain <plain> --edit "<内部名>::<字段>=<值>" --out <out.plain>
python tools/plain_edit.py     --plain <plain> --set <文件绝对偏移>=u32:<值> --out <out.plain>
python tools/stratagem_tune.py --help                # 字段：uses / callin / cooldown

# 封装 / 往返
python tools/dlbin_seal.py seal-key --key <pk> <out.plain> --out <out.dl_bin>
python tools/dlbin_seal.py open-key --key <sk> <out.dl_bin> --out <roundtrip.plain>

# 文档自检
python tools/check_links.py
```

### B. 相关文档

| 主题 | 文档 |
|---|---|
| 密封盒模型与"打不开的那一段" | [DLBIN-SEALED-BOX](../engine/DLBIN-SEALED-BOX.md) |
| 全表字典（55 张表的几何 + 类型库字段树） | [TABLE-DICTIONARY](../tables/TABLE-DICTIONARY-25988413.md) |
| 战备字段总表（面板公式、鹰式次数曲线） | [STRATAGEM-FIELDS](../tables/STRATAGEM-FIELDS-26088801.md) |
| 爆炸 / 弹头 / 外观 | [EXPLOSION-PROJECTILE](../explosions/EXPLOSION-PROJECTILE-25988413.md) · [EXPLOSION-VISUAL](../explosions/EXPLOSION-VISUAL-26088801.md) |
| 实体库（47 MB / 275 块） | [ENTITY-TABLE](../tables/ENTITY-TABLE-25988413.md) |
| 换 build 先做什么 | [BUILDS.md](../../BUILDS.md) |

### C. 署名

本文引用的 `+0x50`（uses）语义、鹰式 `uses_per_rearm` / `rearm_time` 两个字段名，
以及"爆炸行带粒子与音效成员"这条结论，来自 **HD2Runtime by SkyeShade**
（`docs/*`、`core/assets.lua`、`sdk/*.json`；其许可证要求引用偏移/字段名时**显式署名**）。
文中的实机读数与否定证据是本仓库自己的。

### D. 变更

| 日期 | 改了什么 |
|---|---|
| 2026-10-23 | 首版：八步流程、四张表的锚点哈希、宿主选择的三次崩溃、EAGLE 双行案例、16 条坑 |
