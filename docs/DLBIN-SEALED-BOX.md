# `.dl_bin` 封装（sealed box）模型 — 25988413

来源：社区文档 `FOUR-SEALABLE-TABLES.md` + `4tables-plaintext-and-ciphertext.zip`（2026-10-22 收到）。
本文只记录**我们这边独立复现过的**部分，以及**仍然打不开的那一段**。

---

## 1. 结论摘要

| 命题 | 判定 | 依据 |
|---|---|---|
| `data/game/generated_*.dl_bin` = 48 字节封装头 + 密文 | **✓ 实测** | 6 个文件明文大小 + 48 == 磁盘大小，全部吻合 |
| 内层是 LDLD/LTLD 容器，结构与社区文档一致 | **✓ 实测** | 4 张表逐组解析，字节精确消费完 |
| `cipher = plaintext XOR keystream[32:]` | **✓ 实测** | 用一对已知明文/密文求流，解磁盘原文件得到与社区镜像**同 sha256** 的明文 |
| 引擎用的是 libsodium `crypto_box_seal`（X25519+XSalsa20+Poly1305） | **✓ 实测** | `helldivers2.exe` 里 `LibsodiumDRG` / `blake2b` / `curve25519xsalsa20poly1305` / `sysrandom` 四个串相邻 |
| 四张表的密文共用**同一份** 65,536 B keystream | **✗ 否证** | 四个文件 epk 各不相同、各自导出的流从第 0 字节就不同 |
| 不拿到封装材料也能改表并写回 | **⚠ 未能成立** | 见 §4：缺 Poly1305 的 tag 密钥 |

一句话：**能读，暂时不能写**。读这一半已经端到端跑通；写这一半卡在 tag 上，不是格式问题。

---

## 2. 模型

```
文件 = epk(32) || tag(16) || ciphertext          （总长 = 明文 + 48）
ciphertext = plaintext XOR keystream[32:]
```

`epk` 是这条密文自己的 ephemeral 公钥。libsodium 的标准做法是
`nonce = blake2b(epk || recipient_pk, 24)`、`shared = X25519(esk, recipient_pk)`、
XDSA20 输出的**前 32 字节当 Poly1305 密钥**、从第 32 字节起才是用来 XOR 的数据流。

推论（决定"能不能写"）：

- 客户端要解开，就必须持有 `recipient_sk`；**它一定在游戏里**（exe 或 `game.dll`）。
- 要封装一条新的，只需要 `recipient_pk`（公钥），**不需要私钥** —— 而且自己随机一个 ephemeral 就行，
  不受任何长度限制。
- 光有"一对已知明文/密文"只能求出**该文件**的 `keystream[32:]`；`keystream[0:32]`（tag 密钥）永远求不出来。
  ⇒ 用同一条流重新加密是可行的，但 tag 会失效。

## 3. 已验证的证据（可复跑）

### 3.1 48 字节头

| 文件 | 磁盘大小 | 明文（社区/文档） | 差 |
|---|---:|---:|---:|
| `generated_damage_settings` | 50,384 | 50,336 | 48 |
| `generated_planet_color_set_settings` | 2,012 | 1,964 | 48 |
| `generated_planet_types_settings` | 16,892 | 16,844 | 48 |
| `generated_planet_override_settings` | 35,522 | 35,474 | 48 |
| `generated_explosion_settings` | 68,204 | 68,156（文档 §7） | 48 |
| `generated_customization_armor_sets` | 453,252 | 453,204（文档 §7） | 48 |
| `generated_region_settings` | 259,675 | 259,627（文档 §7） | 48 |
| `generated_planet_data` | 369,588 | 369,540（文档 §7） | 48 |
| `generated_zone_data` | 518,526 | 518,478（文档 §7） | 48 |

### 3.2 LDLD 结构（`dlbin_seal.py blocks`）

```
generated_damage_settings  50,336 B  2 groups
  0 LDLD ver=1 type=0xEB1433DA payload=32      off=0x01C
  1 LDLD ver=1 type=0xE0A72CF0 payload=50,252  off=0x054
generated_planet_types_settings  16,844 B  1 group
  0 LDLD ver=1 type=0x857AC132 payload=16,816
generated_planet_color_set_settings 1,964 B 1 group
  0 LDLD ver=1 type=0x9E5B02C2 payload=1,936   = 16 + 30×64
```

三张都对上社区文档 §1/§2/§4 的数字，且每组 payload 之后不留残余字节。

### 3.3 端到端解密（磁盘原文件 → 社区明文）

```
$ python tools/dlbin_seal.py unseal \
    "<游戏>\data\game\generated_damage_settings.dl_bin" \
    --stream refs/dlbin/streams/generated_damage_settings.xor
  plaintext parses as a container: 2 group(s), types 0xEB1433DA, 0xE0A72CF0
wrote damage_from_game.plain.dl_bin (50,336 B, sha256 c28bce58c816a800…)
```

`c28bce58c816a8008ca9e4a761eca624…` 与压缩包 `SHA256SUMS.txt` 里
`plaintext/generated_damage_settings.dl_bin` **完全一致** —— 也就是说这两个工程的明文是同一份。

### 3.4 四对密文不是共用一个 ephemeral

```
$ python tools/dlbin_seal.py pairs D:\mod\work\4tables
4 pair(s), 0 problem(s)
  distinct epk: 4   shared stream: False
```

四个文件各自 32 字节前缀不同，导出的流两两在第 0 字节就分叉。
社区文档 §0 里那份"固定 ephemeral 的 65,536 B keystream"**不是**这四张表用的材料 ——
它是另一个 mod（护甲多被动）自带的封装材料，zip 里没有。

### 3.5 引擎侧密码学

`helldivers2.exe`（28,743,256 B）里连续 0x60 字节内：

```
0x0149AC10  LibsodiumDRG
0x0149AC20  blake2b
0x0149AC28  curve25519xsalsa20poly1305
0x0149AC48  sysrandom
```

正是 libsodium `crypto_box_seal` 依赖的那几样。**打开时会校验 Poly1305 tag**。

---

## 4. 卡在哪：tag

用同一条流重新加密（§5 的 demo 已做），密文长度不变、结构不变，但 `tag` 是覆盖密文的 MAC：

- 只改 4 个字节 → tag 必须重算；
- 重算需要 `keystream[0:32]`，任何"明文/密文对"都给不出这 32 字节；
- 引擎校验 tag ⇒ 拿旧 tag 写进去会在打开时失败。

所以 **"改完写回"这条路目前只有两种走法**：

1. **拿到封装材料**（社区文档说的 `护甲多被动` 里的 `epk/poly/keystream`），
   用它的流 + 它的 poly 重算 tag。上限 65,504 B；
2. **拿到 `recipient_pk`**（公钥即可），自己随机 ephemeral 做标准 `crypto_box_seal`，
   长度不限、tag 自己算 —— 这是真正的通解。私钥在游戏里，公钥可能需要从 exe/`game.dll` 里挖，
   或者从"能正常工作的第三方封装"里反推。

> 注意：文档 §5 的 `seal()` 之所以能用，是因为它手里有 `keystream` 与 `polykey` 两样。
> 我们目前只有"每文件一条流"，没有 polykey。

## 5. 现有工具与产物

```
tools/dlbin_seal.py            pairs | inspect | unseal | seal | blocks | selftest
refs/dlbin/streams/*.xor       4 张表各自的流（由 pair 导出，长度 = 明文长度）
refs/dlbin/streams/report.json epk/tag/流哈希、是否共用一条流
refs/dlbin/pairs/              明文 + 密文原件（含 SHA256SUMS.txt）
refs/dlbin/demo/               见下
```

`seal` 已经能跑，但必须显式给 `--tag`（`copy` / `zero` / 十六进制）。它的用途是：
一旦拿到 polykey，把 tag 填进去就是完整流程。

### demo：改一个雾色并重新封装

```
refs/dlbin/demo/vanilla_generated_planet_color_set_settings.dl_bin   2,012 B  8d671dd3…
refs/dlbin/demo/color_set_red.sealed.dl_bin                          2,012 B  8f4f4e9d…
```

改的是第一条记录的 `ZoneFogMainColor`：`(1.0, 1.0, 1.0)` → `(1.0, 0.0, 0.0)`，
封装后与 vanilla 只差 **4 个字节**（0x66/0x67/0x6A/0x6B），本地解回来 == 修改后的明文。
把 `color_set_red.sealed.dl_bin` 覆盖到 `data/game/` 再启动，就能一次性判定
"引擎是否校验 tag"：

- 星球雾色变红 ⇒ tag 不校验（或校验失败被容忍）⇒ 这条路**立刻通**，不需要任何材料；
- 启动崩溃 / 雾色不变 ⇒ tag 确实校验 ⇒ 必须走 §4 的两条路之一。

还原：把 `vanilla_generated_planet_color_set_settings.dl_bin` 复制回去即可（2 KB，已留档）。

## 6. 上限（如果用材料路线）

keystream 65,536 B、可用明文 65,504 B。超过就够不到，且无法扩展：

| 文件 | 明文 | 状态 |
|---|---:|---|
| `explosion_settings` | 68,156 | 差 2,652 B，够不到 |
| `region_settings` | 259,627 | 3.96× |
| `planet_data` | 369,540 | 5.64×（**星球修饰在这里**）|
| `customization_armor_sets` | 453,204 | 6.92× |
| `zone_data` | 518,478 | 7.92× |

`damage_settings`（50,336）在射程内且余量 15,168 B —— 四张里唯一直接改战斗数值的。

---

## 7. 材料到手（2026-10-22 09:3x，`护甲多被动.zip`）

社区文档说的那份材料就在 `Source/boot.lua` 里，形式是一个自执行函数返回的表：

```lua
local material = (function() return {
    epk       = "\091\188\036...",   -- 32 B
    keystream = "\...",              -- 65,536 B
    poly      = "\...",              -- 32 B
    max_len   = 65536,
} end)()
```

抽出来用 `tools/extract_seal_material.py`（交给 lupa 跑真 Lua 5.1 解析，不手写 `\NNN` 反转义）：

| 项 | 值 |
|---|---|
| `epk` | `5bbc2459cd5f34de62fa11fcf36aa4a37d4fc6a31f91fc761bfb44e559b8a07f` ✓ 与社区文档一致 |
| `poly` | `a37af877af978c5efbe5a8a02a1ca38984584e80d29904c262dfd3c9844680a7` ✓ 一致 |
| `poly == keystream[:32]` | **True** ✓（libsodium 的 XSalsa20-Poly1305 布局自洽）|
| 可用明文上限 | 65,504 B |

产物：`refs/dlbin/material/{keystream,epk,poly}.bin` + `material.json`（含 sha256）。

### 7.1 交叉验证：Lua 实现与我们的 Python 逐字节相同

从 `boot.lua` 里把 `poly` / `material` / `sealer` 三段自执行块抠出来，在 lupa 里调它的 `seal()`，
与 `dlbin_seal.py seal-material` 对同一批输入比较：

```
  0 B / 1 B / 11 B / 1000 B / 65504 B / 真实 color_set 明文
  → 6/6  identical = True
```

两套独立实现、同一材料、逐字节一致 —— 说明封装构造（tag 覆盖 cipher，不含 epk）没有理解错。

### 7.2 首个写回（已部署，待实机）

`generated_planet_color_set_settings.dl_bin`：30 条记录的 `ZoneFogMainColor` 全部改成 `(1,0,0)`，
用材料重新封装（2,012 B，tag `82f932933936ad7eacf7fa091e06d144`），已写入 `data/game/`。

- 期望：进任务后地表雾变红
- 回滚：`cp refs/dlbin/demo/vanilla_generated_planet_color_set_settings.dl_bin "<游戏>/data/game/generated_planet_color_set_settings.dl_bin"`

> §5 那个"旧 tag"实验因此作废 —— 现在 tag 是算出来的，不需要赌引擎是否校验。

#### 7.2.1 首次写回结果：启动后崩溃（2026-10-22 09:37，待判别）

改红的那份写进 `data/game/` 后，游戏**启动过一次**（`BootProbe.log` 09:36:56 有一条完整记录，
说明 boot 阶段跑完了），随后崩溃，THEIA 转储 9,349,719 B：

| 项 | 值 |
|---|---|
| 异常码 | `0xC000000D`（STATUS_INVALID_PARAMETER），参数个数 0 |
| 故障 RIP | `ntdll.dll+0x86BE7` |
| THEIA 自定义流（0x30524B50）| UTF-16 路径 `...\Helldivers 2\bin\runtime.dll` |
| 栈（自顶向下）| ntdll ← PlayFabMultiplayerWin ← ucrtbase ← **runtime.dll+0x57A4D2** ← helldivers2.exe ← `level_generation_pluginw64_release.dll` |
| 转储内存（5,011,922 B / 2,420 段）| 无 `generated_` 路径、无 `sealed`/`crypto_box`、无我方 epk；只有 1 处 `LDLD` 落在栈上 |
| 线程 | 转储里只有 1 个线程（此前 10-20 的三次崩溃是 67–71 个线程）|

工作区已于 09:39 还原成原版（`8d671dd3…`）。

**判别方法（隔离实验）**：用**完全相同的原版明文**重新封装（只换 epk/tag，内容一字不动），
`refs/dlbin/demo/color_set_resealed_same_content.sealed.dl_bin`（2,012 B，`57177ff1…`）。

- 能正常进游戏 ⇒ 封装本身被接受，之前的崩溃与封装无关（是内容改动或偶发）；
- 同样崩 ⇒ 这一版对"封装来自谁"另有校验（旧 tag/固定 ephemeral 可能被拒）。

#### 7.2.2 结论（2026-10-22 09:5x）：崩在**第二层内容哈希**

`HD2-Mod-Developer-Guide-25988413.zh-CN.txt` §8 写明：认证封装与引擎内容校验是**两层**，
引擎还会比对 `MurmurHash64A(明文)` 与内置预期值（seed `0xDEADBEEFABAD1DEA`、
乘数 `0xC6A4A7935BD1E995`、shift 47）。封装正确但内容哈希不对 → 引擎报 `0xC000000D`。

我们已独立实现并**用已知值验证**（`tools/murmur64a.py`）：

| 检查 | 结果 |
|---|---|
| 被动明文 sha256 | `6ba67061…8ad40` = 指南附录 A ✓ |
| 该明文 MurmurHash64A | `BFB6F7235F9A269C` = 指南附录 A ✓ |

**哈希不改只能靠"填充字"**：把某个 8 字节对齐、语义为空的 word 反解成让总哈希保持不变的值。
作者的 `passive_example.py` 用的是"某个组头 `+16` 那个对齐 word"（1 字节 Is64Bit + 7 字节保留区），
并用首个组头的两个保留字节做搜索旋钮、要求解出来的低字节仍是 1。

对齐扫描（我们的 5 张明文）：

| 表 | 组数 | 可用的对齐填充 word |
|---|---:|---|
| `customization_passive_bonuses` | 33 | **7 个**（如 0x9F0）|
| `damage_settings` | 2 | **0** |
| `planet_override_settings` | 13 | **0** |
| `planet_types_settings` | 1 | **0** |
| `planet_color_set_settings` | 1 | **0** |

⇒ 雾色表（1 组、组头 @0x4，`header+16=0x14` 不对齐）**根本不可能同时改内容又保哈希**，
那次崩是必然的，不是封装问题。

#### 7.2.3 用作者示例做的第一次合法写回（已部署，待实机）

```
kit/tools/passive_example.py --input <被动原明文> --extra-id 7 --output passives.medkit.plain
  → 4,016 B → 4,992 B，内容哈希不变 BFB6F7235F9A269C（33 组）
dlbin_seal.py seal-material → 5,040 B，tag 1c984dae27a2729770c4acd3a0a7f98c
  回验：解封 == 作者产出的明文，33 组，哈希不变
```

已写入 `data/game/generated_customization_passive_bonuses.dl_bin`（5,040 B，md5 `ae8e20dc…`）。
预期效果：**急救包（ID 7）+2 支兴奋剂**，非零被动的护甲都应变成 6 支。

回滚：`cp refs/dlbin/demo/vanilla_generated_customization_passive_bonuses.dl_bin "<游戏>/data/game/"`
（原版 `91cfc2bf…`）

#### 7.2.4 对另外三张表的含义

`damage` / `planet_override` / `planet_types` 没有对齐的组头填充字，若要用，
必须像指南 §8.1 的载具示例那样**改用记录级填充**（先解析类型库 `LTLD` 拿到字段偏移与 padding）。
在那之前，这三张表都改不了 —— 不是封装问题，是没有可承载哈希校正的空闲字节。

另一条路仍是拿到 `recipient_pk`：指南 §4.2 给了旧构建初始化映像的两个 RVA
（公钥 `0x16532B0`、私钥 `0x1653160`，四段 qword 各 XOR `0xEB63463F0C116E2C`），
但那是**解包后的映像**；我们的旧备份 exe 是 aPLib 打包的，需要先离线还原该层。

---

## 10. 拿到接收方密钥对：用旧构建的全量内存转储绕过 aPLib（2026-10-22 09:5x）

指南说那些 RVA 是**加载后映像**的地址 ⇒ 不需要解包器，只要有一份旧构建运行时的**全量转储**。
`E:\hd2-dumps\kept\crash-125128-pid18524-full.dmp`（10.3 GB，2026-10-18，build 25480438）正是。

`tools/dump_read_rva.py` 直接按模块基址 + RVA 定位（10 GB 文件只 seek，不整读）：

```
module helldivers2.exe: base 0x7ff767470000, size 0x39e8000
<这一行是密钥材料，已从历史中抹除>
<这一行是密钥材料，已从历史中抹除>
按四段 LE qword 各 XOR 0xEB63463F0C116E2C 拼接：
<这一行是密钥材料，已从历史中抹除>
<这一行是密钥材料，已从历史中抹除>
```

### 10.1 三重验证

| 检查 | 结果 |
|---|---|
| `X25519(sk) == pk` | ✓ 且与映像里的 pk 片段逐字节一致 |
| 用 sk 解当前 build 的原版被动文件 | 4,016 B，sha256 `6ba67061…` = 指南附录 A ✓ |
| 解出的类型库明文 sha256 | `a2392b58c80a2a70…` = 指南附录 A ✓ |
| 解出的战备表内容哈希 | `04BBE33EF809862A` = 指南附录 A ✓ |

密钥对存于 `refs/dlbin/keys/`（`.sk` / `.pk` / `keys.json` 记了来源 RVA 与验证结果）。

### 10.2 能力变化

- **65,504 B 上限消失**：`dlbin_seal.py seal-key` 用公钥 + 全新随机 ephemeral 做标准
  `crypto_box_seal`，长度不限。
- **全表可读**：`open-key` 解出任意 `data/game/*.dl_bin`。已解到 `refs/dlbin/plaintext-all/`：

| 文件 | 密文 | 明文 | 组数 / 备注 |
|---|---:|---:|---|
| `generated_zone_data` | 518,526 | 518,478 | 非 LDLD 容器 |
| `generated_customization_armor_sets` | 453,252 | 453,204 | 422 组 |
| `generated_planet_data` | 369,588 | 369,540 | 非 LDLD 容器（**星球修饰在这里**）|
| `generated_region_settings` | 259,675 | 259,627 | 非 LDLD 容器 |
| `generated_projectile_settings` | 96,652 | 96,604 | 1 组 |
| `generated_stratagem_settings` | 82,432 | 82,384 | 12 组 |
| `generated_explosion_settings` | 68,204 | 68,156 | 1 组 |
| `generated_damage_settings` | 50,384 | 50,336 | 2 组 |
| `generated_weapon_customization_settings` | 30,872 | 30,824 | 9 组 |
| `generated_customization_passive_bonuses` | 5,040 | 4,992 | 33 组（**当前部署的是 medkit 版**）|
| `dl_library.dl_typelib` | 1,080,072 | 1,080,024 | LTLD v4 类型库 |

### 10.3 仍然要过的那一关

长度不再是问题，**内容哈希仍是**：改完必须让 `MurmurHash64A(新明文)` 等于引擎内置的预期值
（= 原明文的哈希），手段仍是"把某个语义为空的 8 字节对齐字反解成校正值"。
现在的进展是：**类型库明文已经拿到**，可以按类型描述符把每张表的字段偏移与 padding
逐项读出来，不再靠猜 —— 这是给 `damage` / `planet_*` 找校正区的下一步。

---

## 11. ✓ 实机验收：哈希保持的写回被接受（2026-10-22 10:0x）

`generated_customization_passive_bonuses.dl_bin` 换成"每条非零被动追加急救包"的版本后启动：

- 屏幕左下兴奋剂显示 **×6/6**（原版 4 支）⇒ 追加的 PM/SM 生效；
- 游戏正常加载，未崩 ⇒ **内容哈希保持 + sealed box 认证两层都过**。

这是本项目第一次成功改写**引擎加密并做内容校验**的磁盘资源。链路：
`原明文 → 语义修改 → 反解填充字保住 MurmurHash64A → 用接收方材料/密钥封装 → 写盘 → 引擎接受`。

> 注意：写回的是"哈希保持"版本。若把任意改写（如雾色表）直接封装写盘，引擎会在内容校验处拒绝
> （`0xC000000D`），与封装无关。

### 11.1 待验证：全新 ephemeral

`refs/dlbin/demo/passives_medkit_fresh_epk.sealed.dl_bin`（5,040 B，`e8cf87f3…`）内容与已验收版
完全相同，但用**我们自己的随机 ephemeral**（epk `521a080a…`）标准封装，而不是护甲材料那条固定流。
换上去若仍是 6/6，说明封装能力已完全独立。

---

## 12. 类型库解析与"可编辑性"审计（2026-10-22 10:2x）

`tools/typelib.py` 解析 LTLD v4（`refs/dlbin/plaintext-all/dl_library.dl_typelib`）：

```
LTLD v4  types=1208  enums=345  members=7349  enum_values=9072  字符串表 0 B
```

**字符串表为空**（指南 §5.2 已说）：类型名不可读，只能按 `0x????????` 哈希 + 尺寸/成员结构辨认。
索引已存 `refs/dlbin/typelib-index.json`。

### 12.1 审计规则

改内容必须保住 `MurmurHash64A`，只能用"语义为空的 8 字节对齐字"来反解。两个来源：

1. **组头 word**：`header+16` 那个 8 字节（1 字节 Is64Bit + 7 字节保留区）。要求它在文件里 8 字节对齐，
   且解出来的低字节仍为 1；搜索旋钮用第一个组头的保留字节。
2. **记录级 padding**：类型描述符里没有任何成员覆盖的字节，取其中完整的 8 字节对齐字。

### 12.2 结果（`typelib.py audit`）

| 表 | 组数 | 可用校正字 | 判定 |
|---|---:|---:|---|
| `customization_passive_bonuses` | 33 | **7** | ✓ 已实测可改（6/6 兴奋剂）|
| `stratagem_settings` | 12 | **4** | ✓ 可改（**新解锁**：战备冷却/次数）|
| `weapon_customization_settings` | 9 | **4** | ✓ 可改（**新解锁**：武器改装数值）|
| `damage_settings` | 2 | 0 | ✗ 组头都不对齐；元素类型 `0x260CBE2B`（76 B / 8 成员）**零 padding** |
| `customization_armor_sets` | 422 | 0 | ✗ 组类型不在类型库里，记录 padding 无法判定 |
| `projectile_settings` | 1 | 0 | ✗ 同上 |
| `explosion_settings` | 1 | 0 | ✗ 同上 |
| `planet_data` / `region_settings` / `zone_data` | — | — | ✗ **不是 LDLD 容器**（解析报 trailing bytes / bad magic），需要先认容器格式 |

`DamageSettings` 的根结构是 16 字节 `<qQ>`（数组偏移+数量），元素类型 `0x260CBE2B`：76 字节、
8 个成员、覆盖满、**没有一字节空隙**。所以这张表在当前方法下确实改不了 —— 不是没找对地方。

### 12.3 老路线的对应恢复

- **战备冷却/次数**（旧 build 用内存改的那类）→ 现在可以离线改 `stratagem_settings`；
- **武器改装数值** → `weapon_customization_settings`；
- **护甲被动** → 已通；
- **伤害/穿甲** → 仍需别的手段（该表无空隙）；
- **载具/敌人** → `entities`、`planet_data` 结构未解。

---

## 13. 补齐缺失类型：fileDiver 的 `datalibrary/`（2026-10-22 10:3x）

我们类型库里 1208 个类型没有名字、也缺 4 个组类型。外部补齐来源：

| 来源 | 内容 | 用法 |
|---|---|---|
| 本地 `filediver-dl-type-names.txt` | 6,698 个类型名 | 按 DJB2 反查哈希 → 给类型库命名 **1077/1208** |
| `xypwn/filediver/datalibrary/*.go`（323 个文件）| 每个类型的 Go 结构定义，**含显式 padding 字段** | 补布局：`armor_sets.go`、`explosion_settings.go`、`projectile_settings.go` 已下到 `D:/mod/work/filediver/` |

### 13.1 组类型全部按名确认

| 表 | 组类型哈希 | 名称 |
|---|---|---|
| `customization_armor_sets` | `0xD9A55AA0` | `HelldiverCustomizationKit` |
| `projectile_settings` | `0xBD4042C2` | `ProjectileSettings` |
| `explosion_settings` | `0x2AEA2592` | `ExplosionSettings` |
| `weapon_customization_settings` | `0x1E604234` | `WeaponCustomizationSettings` |
| `stratagem_settings` | `0x30EB6399` | `StratagemSettings` |
| `damage_settings` | `0xEB1433DA` / `0xE0A72CF0` | `DamageArmorAngles` / `DamageSettings`（元素 `DamageInfo` = `0x260CBE2B`）|

### 13.2 ★ 记录里确实有 padding

之前 `audit` 报"0 个可用校正字"，原因是**类型库不含这些类型、布局未知**，不是真的没有空隙。fileDiver 的结构里显式写着：

| 类型 | padding 字段 |
|---|---|
| `Piece`（armor 的部件记录）| `_ [4]uint8`（偏移 16）、`_ [7]uint8` |
| `Body` | `_ [4]uint8` |
| `CamoflagePiece` | `_ [4]uint8` |
| `rawExplosionInfo` | `_ [3]uint8`、`_ [4]uint8`、`_ [3]uint8`、`_ [3]uint8`、`_ [4]uint8`、`_ [4]uint8` |
| `rawProjectileInfo` | `_ [4]uint8`、`_ [4]uint8`、`_ [3]uint8` |

`HelldiverCustomizationKit` 本身 64 B **无空隙**（`Id4 DlcId4 SetId4 NameUpper4 NameCased4 Description4 Rarity4 Passive4 Archive8 Type4 Unk004 BodyArray16`），
但它的嵌套数组里的 `Piece` 有 padding ⇒ 校正字应该从嵌套数组里找。

**下一步**：按 Go 结构把嵌套数组的文件偏移算出来，挑 8 字节对齐的 padding 字，
再跑一遍"改 + 保哈希 + 封装"（armor_sets 422 条、projectile、explosion 三张表大概率能打开）。
`DamageInfo`（76 B / 8 成员）确认零 padding，`damage_settings` 仍无解。













### 7.3 顺带拿到的第 5 张表

`boot.lua` 里还内嵌了 `generated_customization_passive_bonuses.dl_bin` 的原始明文与密文
（`ORIGINAL_PLAINTEXT` / `ORIGINAL_SEALED`）；`Recovery/profiles/000.dl_bin` 与我们游戏里的
同名文件**逐字节相同**（`91cfc2bf…`）。这张表（4,016 B）也在 65,504 以内。

### 7.4 射程更新

| 能改（≤65,504） | 明文 | 备注 |
|---|---:|---|
| `damage_settings` | 50,336 | 唯一直接改战斗数值，余量 15,168 |
| `planet_override_settings` | 35,474 | 1,351 条资源替换 |
| `planet_types_settings` | 16,844 | 星图外观 |
| `customization_passive_bonuses` | 4,016 | 护甲被动 |
| `planet_color_set_settings` | 1,964 | 雾色 |

仍够不到：`explosion_settings`（68,156，差 2,652）、`region` / `planet_data` / `armor_sets` / `zone_data`。

**要突破长度上限**：不需要私钥，只要拿到 `recipient_pk`（游戏公钥）—— 自己随机 ephemeral 做标准
`crypto_box_seal`，tag 自算、长度不限。公钥可从 exe/`game.dll` 里挖，或从别人能正常工作的封装反推。

