# 社区案例研究（2026-10-21，build 25988413）

来源：`D:\Downloads\案例\` 三个包。目的：找昨晚（10-20）判断里漏掉的路。

## 1. ★ 最重要的发现：`.patch_N` 能替换**任意资源类型**，不需要 codec

### 1.1 案例

`FRV防翻转（无LUA版本）.zip` —— 纯文件 mod，**没有 Lua、没有 loader、没有脚本**，
替换三台 FRV 的**物理资源**，作者明确标注适配 build 25988413（10-20 更新）。

README 声称改动（stock 括号内）：
质量 3990/4000/3975（3000/2500/7500）、重心高度 -0.6（-0.375）、
轮胎抓地 1.2/1.1（1.0/0.9）、轮径 0.62（0.55）、阻尼 1.25/1.25（0.75/1.25）、
悬挂行程 5.5/7.5（4.0/6.5）。

### 1.2 拆包结果（实测）

补丁 `9ba626afa44a3aa3.patch_0` 含 **3 个条目，类型全是 `0x5f7203c8f280dab8` = `physics`**：

| file id | toc 大小 | 内含字符串 |
|---|---|---|
| `0xcc21c7ffd3ebefb9` | 264,208 B | `divers/vehicles/frv/frv` |
| `0x9b2140378640432e` | 307,504 B | `s/frv_supply/frv_supply` |
| `0x2d85bfe3d8717fe5` | 282,064 B | `es/frv_heavy/frv_flamer` |

**负载是裸 float32，固定偏移，无压缩无加密**（熵 5.52 / 5.62 / 5.62）：

```
id=0xcc21c7ffd3ebefb9:
  0x110 : 3990.0     ← 质量
  0x150 : -0.6       ← 重心高度
  0x3cf34 : 1.2  0x3cf38 : 0.62  0x3cf64 : 15.0  0x3cf6c : 5.5
  0x3cf68 : 1.25 0x3cfa4 : 1.2   0x3cfdc : 5.5 ...
  → 四个轮子，步长 0x70，前/后两组
id=0x2d85bfe3d8717fe5 里还留着 stock 的 -0.375 @ 0x6b80（说明另有字段未改）
```

toc_data 布局：`[type_id(8)][file_id(8)][dword=自身长度][资源头 ...]`，`SDKV` 标记在偏移 700–716。

### 1.3 我们昨晚错在哪

昨晚的结论是「47 种资源里只有 5 种有 codec（bones/lua/texture/mesh/material），
所以只能改这 5 类」。**这是把「能理解结构」和「能替换资源」混为一谈了。**

- **codec** 只用于*读懂/改结构*；
- **`.patch_N` 替换**只需要**原始字节** —— 引擎不管那堆字节是什么类型，有对应类型的加载器就行。

⇒ 只要我们能拿到某个资源的原始字节、知道（或猜中）目标值的位置，就能改。
**这条路上 EAC 不拦**（社区 mod 正常分发、正常启用）。

### 1.4 立刻可做的事

1. 我们的 `srkit.modkit.build_patch()` 目前**只支持 lua**（内部写死 `TYPE_LUA` 并把源码包成 `[len][mode]`）。
   底层 `TocEntry` / `Package` 是通用的 ⇒ 需要补一个「按任意 type + 原始字节建补丁」的函数；
2. 回归验证：把 FRV 的 physics 负载**原样重打包** → 游戏是否仍然接受；再改一个 float → 观察效果。
   这一步一旦通过，我们就具备了**自主产出非 Lua 资源 mod** 的能力。

## 2. `data/game/` 下有整套玩法数据表（就是我们找的"行表"的磁盘形态）

```
generated_damage_settings.dl_bin                 50,384 B   伤害
generated_projectile_settings.dl_bin             96,652 B   弹丸
generated_explosion_settings.dl_bin              68,204 B   爆炸
generated_customization_passive_bonuses.dl_bin    4,064 B   护甲被动
generated_customization_armor_sets.dl_bin       453,252 B   护甲套装
generated_weapon_customization_settings.dl_bin   30,872 B
generated_stratagem_settings.dl_bin              82,432 B
generated_entities.dl_bin                    47,259,444 B   实体
... 共 50+ 个文件，另有 dl_library.dl_typelib (1,080,072 B)
```

**但**：全部 `generated_*.dl_bin` 熵 **8.000**、无 magic、zlib/lz4/zstd 全部解不开
⇒ **压缩或加密**，目前不可读。这是下一步要攻的点。

判定方向：
1. 用**旧 build 的同名文件**对比（`D:\mod\build-25480438-pre-update\` / `build-snapshot-25988413-post-update\`）：
   - 同名文件字节相同 ⇒ 密钥是固定的（跨版本），可从别的途径求；
   - 同名文件字节不同 ⇒ 每次构建重加密（密钥可能来自 exe），难度大。
2. 判断加密 vs 压缩：压缩数据会有块结构，加密没有；试全部常见容器。
3. 若加密：`dl_library.dl_typelib` 也加密吗？密钥是否藏在 `game.dll`/`helldivers2.exe` 里。

## 3. `data/game/game.dll` = 49,075,800 B，**是 MZ/PE 文件**

熵 8.000（代码段可能压缩/加密），但文件头是标准 `4D 5A 90 00`。
BSL 作者文档也确认它是「游戏模块」且核对过 SHA256 —— 说明**文件可稳定读取**。
⇒ 静态分析时它比 `runtime.dll` 更值得优先（runtime.dll 有 packer0..4）。

## 4. BSL Lua51 0.1.0 文档：与我们的做法一致，没有新能力

核对项：重建 `boot`（资源哈希 `f476df93691895fa`）、源码载荷 `[len][mode=2][source]`、
`can_get('lua', name)`、纯 Lua MurmurHash64A、去掉 ffi/jit。
他们明确写了「没有恢复 ffi / bit / 原生调用」。实机证据只到「加载成功 + 60 次 update 回调」。
⇒ **不改变我们的结论**，但可以引用它的运行时门槛（EXE 28,743,256 B / game.dll 49,075,800 B）。

## 5. yoidore 包：没有 native 加载路径

- `native_backend_incident.json` / `Companion` 指的是**游戏外**的 .NET `System.Media.SoundPlayer`
  音频程序，靠**日志文件当 IPC**（Lua 写日志 → 外部程序读 → 播音乐）；
- 它自己的验证记录写着 `game_verified: false`（lupa 模拟环境验的）；
- 两个可借鉴点：
  1. **`render` 回调也被包装**（我们的加载器只挂 `update`）—— 画 HUD 时可能更稳；
  2. 文件 IPC 桥接思路（游戏内 Lua ↔ 游戏外程序）。

## 6. 结论：昨晚漏掉的两条

| # | 漏掉的东西 | 影响 |
|---|---|---|
| 1 | **任意资源都能被 `.patch_N` 替换**，不需要 codec | 载具/物理类数值 mod 现在就能做；其余类型只差"知道值在哪" |
| 2 | `data/game/*.dl_bin` 是玩法数据表的磁盘形态 | 若解开，可能直接给出伤害/弹丸/护甲行表；当前被加密/压缩挡住 |

## 7. 补充判定：`dl_bin` 是"松文件 + 已加密"，不是资源

```
bundle_database.data 里 grep "generated_damage_settings" / "generated_entities" / "dl_typelib" → 全部 0 命中
```

⇒ 这 50+ 个 `.dl_bin` **不经过资源库**，是引擎的"data library"按**路径**从 `data/game/` 直接读的松文件。
⇒ **`.patch_N` 覆盖资源的路子对它们无效**；要改只能替换磁盘上的文件本身。

加密判定（不是压缩）：

| 验证 | 结果 |
|---|---|
| zlib / raw-deflate（wbits −15/15/31，偏移 0/4/8/12/16/20） | 全部解不开 |
| gzip / zstd / lz4 magic | 无 |
| 前 4 个 dword 形态 | 随机，无长度/魔数结构 |
| 熵 | 8.000（164 B 的小文件也是）|

⇒ **已加密或自定义加密容器**。要读它必须拿到密钥/算法；线索在 `game.dll`（49 MB，MZ 头但熵 8.0）
或 `helldivers2.exe`（28.7 MB）里。

**注意**：这也意味着即使解开，改它需要**替换松文件**（`data/game/*.dl_bin`），
而不是打补丁 —— 风险面（EAC 是否校验这些文件）与 `.patch_N` 完全不同，需要单独评估。

---

## 8. 落地：通用资源补丁构造器（2026-10-21 15:45）

### 8.1 案例的字节级实现

补丁 `patch_0`（854,120 B）含 3 个 `physics` 条目，每条 `toc_data` 布局：

```
[type_id 8][file_id 8][dword = 自身长度][资源头(约 700 B)][SDKV20190100 ... 负载]
```

`Package.to_bytes()` 是**原样写入 toc_data**，所以「补丁 = 把资源原始文件塞进归档」。
引擎侧按类型选加载器，物理加载器读的就是这份裸数据。

负载是 **float32 数组**。**下面这张表是 2026-10-21 20:2x 按「stock 资源 vs 社区补丁」逐 float 对拍得到的**
（三台车各 **16 个 float / 36 字节**，三台完全同构，以 `frv/frv` 为例）：

| 偏移 | stock → 新值 | 含义 |
|---|---|---|
| `0x120` | 3000 → 3990 | **质量（kg）**（M-103 2500→4000，M-104 7500→3975）|
| `0x160` | −0.375 → −0.6 | **重心高度**（越低越不容易翻）|
| `0x3cf44` | 1.0 → 1.2 | 抓地（前 1 号轮）|
| `0x3cf48` | 0.55 → 0.62 | 轮径（前 1 号轮）|
| `0x3cf78` | 0.75 → 1.25 | **阻尼**（前 1 号轮）— README 说这才是防翻的真修 |
| `0x3cf7c` | 4.0 → 5.5 | 悬挂行程（前 1 号轮）|
| `0x3cfb4` … `0x3cfec` | 同上 4 项 | 前 2 号轮（**步长正好 0x70**）|
| `0x3d024` / `0x3d094` | 0.9 → 1.1 | 抓地（后 1 / 2 号轮）|
| `0x3d028` / `0x3d098` | 0.55 → 0.62 | 轮径（后 1 / 2 号轮）|
| `0x3d05c` / `0x3d0cc` | 6.5 → 7.5 | 悬挂行程（后 1 / 2 号轮）|

未改：弹簧（前 15 / 后 18）、后轴阻尼（stock 就是 1.25，无需改）。

> **订正（2026-10-21）**：本节早先的偏移表有两处错 ——
> ① 质量/重心/抓地等偏移**小了 0x10**（旧表 `0x110`/`0x150`/`0x3cf34`，实际 `0x120`/`0x160`/`0x3cf44`）；
> ② 后轴偏移**整条是错的**（旧表写 `0x4070c`/`0x40790`，实际在 `0x3d024` 之后）。
> 另外旧表说"阻尼（前/后）都改成 1.25"，实际**只改了前轴** —— 后轴 stock 已经是 1.25。
>
> ⚠ **轮子参数的块偏移每台车都不同**（`0x3cf44` / `0x47864` / `0x41504`），
> 所以**不能写死偏移**，要按"轮子记录"的字段模式搜索（质量那条 `0x4A182741` 标记同理，见 §17）。

### 8.2 我们的工具（`D:\mod\tools\resource_patch.py`）

```
list   <patch>                      列条目（type/id/size/head）
dump   <patch> <id|idx> -o FILE     原样导出某条目 toc_data
repack <patch> -o DIR --index N     按原条目重建补丁（回归）
build  <spec.json> -o DIR --index N 用任意 (type,id,payload) 建补丁
```

**回归结果**（按社区补丁自身条目重建）：结构一致，总长差 **8 字节**，差异只有两处：

1. 包头 `unk4_data`（0x10 起 56 字节）社区工具写了指纹，我们写零；
2. 负载偏移 8/16 字节对齐差（社区写 0x158，我们写 0x160）。

这两处**不影响可用性** —— 我们所有 lua 补丁一直是零指纹 + 16 对齐，游戏照常加载。

### 8.3 能力边界（第一批实测）

| 资源类型 | 游戏内数量 | 是否明文 | 证据 |
|---|---:|---|---|
| `physics` | 39,172 | ✓ 裸 float32 | FRV 案例；熵 5.5 |
| `lua` | 1,046+ | ✓ 源码 | 我们一直在用 |
| `network_config` | 1 | ✓ rpc 名 + 字段记录 | 10-20 解出 595 个 rpc 名 |
| `config` | 3 | ✓ 有字段名 + 数字 | 熵 3.398；`device_type`/`threshold`/`input_type` |
| `mesh`（= unit 资源，srkit 有 codec）| 48,020 | 待验（后台解码中）| — |
| `texture`/`material`/`bones` | 50,582 / 50,152 / 4,912 | codec 有 | srkit |
| `data/game/*.dl_bin` | 50+ | ✗ 加密 | 熵 8.0、deflate/lz4/zstd 全失败；且**不是资源**（不在 bundle_database）|

### 8.4 由此可以做的 mod（已证实 / 待验）

- **已证实可行**：载具物理（质量/重心/抓地/阻尼/悬挂/轮径）。物理资源 39,172 个，不止载具 ——
  道具、植被、可部署物的物理也在其中。
- **已证实可行**：任何 Lua 逻辑（源码补丁）。
- **待验（最高价值）**：`unit` 资源里是否含武器/护甲组件数据；若有且 srkit 能解码，
  则伤害/弹丸/护甲数值可以**纯资源侧**改，完全不需要内存。
- **边界外**：`dl_bin`（加密松文件）、需要 GPU 数据重建的贴图链。

---

## 9. 节点/骨骼：发射点确实在资源侧（2026-10-21 16:10）

### 9.1 三层分工（实测）

| 资源 | 存什么 | 证据 |
|---|---|---|
| `bones` (0x18DEAD01056B72E9) | **骨骼名字** + 哈希 + LOD 距离 + 每级骨骼数。**没有位置** | Scythe bones：20 根、6 级 LOD、403 B、熵 5.6 |
| `unit` (0xE0A48D0BE9A7453F) | `transform_info`：每个节点的 **position/rotation/scale/parent_bone/name_hash** + 4x4 矩阵 | Scythe unit：40 个节点 |
| mesh 几何 | 顶点/索引（在 `gpu_resources`）| Scythe gpu 811,708 B |

### 9.2 命名规则（已验证 6/6）

**骨骼名 = murmur64(name) 的高 32 位**（与资源名同一套 IdString32）：

```
murmur64("muzzle") = 0x2C8ECE2B1CF8FAC9 → 高32位 0x2C8ECE2B = 747556395
Scythe bones 里: {"index":11, "hash":"747556395", "name":"muzzle", "name_matches_hash":true}
```

`elevation` / `traverse` / `barrel` / `game_mesh` / `weapon_pitch` 逐一对上。

### 9.3 LAS-5 Scythe 的节点树（`0x27EE1ED8F6FB6356`，hashlist 反查确认）

```
StingrayEntityRoot → FbxAxisSystem_ConvertNode → laser_rifle(3)
   ├ skeleton(9) → root(10) → boss(11)
   │     ├ attach_optic [0,-0.047,0.182]      ├ sight [0,-0.198,0.194]
   │     ├ cog [0,0.085,0.103]                ├ attach_muzzle [0,0.466,0.119]  ← 发射点
   │     ├ attach_ammo / attach_mag / attach_mag_2 / attach_underbarrel / attach_paintjob
   │     └ IK_left / IK_right
   ├ shadow_mesh(4) → g_body_shadow LOD1-3
   ├ collision(29)  → c_body / c_culling
   └ game_mesh(33)  → g_body / LOD1-4
```

bones 里另有一根叫 `muzzle` 的骨骼（哈希 `0x2C8ECE2B`）；unit 的 transform 树里是 `attach_muzzle`
（哈希 `1464994495`）。两者都存在，发射点最终取哪一个待实验判定。

### 9.4 transform 段的二进制布局与"外科手术"改法

```
offset+0:   u32 count
offset+4:   12 字节填充
offset+16:  count × 64 字节  { rotation 9f | position 3f | scale 3f | 对齐 1f }
其后:       count × 16f 矩阵
其后:       count × (u16 increment, u16 parent_bone)
其后:       count × u32 name_hash
```

节点 i 的 position 字节偏移 = `transform_info_offset + 16 + i×64 + 36`。

**不要整体重编码**：`UnitCodec` 往返会少 20 字节（section 偏移被重算）。
正确做法是**原地改 12 字节**，其余字节一个不动（Scythe 实测只改 4 字节）。

### 9.5 单元资源打补丁必须带 gpu 数据

unit 资源的顶点/索引在 `gpu_resources` 里。只给 toc 不给 gpu ⇒ 武器可能加载失败或不可见。
`tools/resource_patch.py build` 已支持 spec 里的 `"gpu"` / `"stream"` 字段。

### 9.6 已就绪的实验（等实机）

`mods-spike/scythe_muzzle/build/9ba626afa44a3aa3.patch_3`（toc 13,536 B + gpu 811,708 B）：

- 把 **LAS-5 Scythe 的 `attach_muzzle` 节点抬高 1.5 米**（0.466 → 1.966），只改 4 个字节
- 预期：开枪时枪口闪光/弹道起点出现在枪管上方 1.5 米处
- 若生效 ⇒ **武器节点位置完全可控**，包括"给没有模型的炮塔凭空定义发射点"

### 9.7 对旧实验的解释

载具上那个无网格激光炮头"缩在车底、跟着载体走"：它的 unit 资源里**没有自己的节点树**
（没有 transform 节点），引擎回退到父级（载具）节点 ⇒ 位置随载体、且模型无处安放。
这与 §9.1 的三层分工一致。

### 9.8 第二个武器交叉验证（AR-23 Guard Dog Weapon，`0xA32621E3BDE13379`）

```
27 个节点，11 个 mesh，bones_ref=0xA32B...（非零）
  #11 'attach_muzzle' parent=10 pos=[0.0, 0.385, 0.127]
  #13 'attach_mag'    parent=10 pos=[0.001, -0.187, 0.109]
```

与 LAS-5 Scythe 完全同构 ⇒ **`attach_muzzle` / `attach_mag` 是武器的统一命名约定**，
不是某一把枪的特例。发射点节点由名字约定 + 资源内 transform 共同决定。

---

## 10. 第三方实例佐证：`热熔加长`（2026-10-21 17:05）

分发包 `D:\Downloads\热熔加长.rar`（401 KB，2026-09-02），归档到 `refs/cases/rong_27/`。
补丁 `patch_27`（14,904 B）+ gpu 11,335,080 B，含 **3 个条目，全部同一个 id `0x6CFCC7F8801A0266`**：

| 类型 | 大小 | 内容 |
|---|---|---|
| `bones` (0x18DEAD01056B72E9) | 236 B | 9 根骨骼：StingrayEntityRoot / attach_mag / front_grip_hinge_01/02 / mag_hinge / hose_jiggle_01/02 / trigger |
| `state_machine` (0xA486D4045106165C) | 1,452 B | 状态机（无 codec，原样）|
| `unit` (0xE0A48D0BE9A7453F) | 12,808 B | 36 个节点 |

> **订正（2026-10-21，索引建好后核出）**：`unit` 的 **stock** 资源是 **12,304 B**，社区补丁里是
> **12,808 B** —— 他们的工具重写过这个资源，**比 stock 多 504 B**，两者从偏移 `0x5C` 就开始不同。
> `bones`(236 B) 与 `state_machine`(1,452 B) 两份我们读到的 stock 与补丁**逐字节同尺寸**，
> 所以偏差只出在 unit 上。⇒ 文件级改动**不要照抄社区的重编码结果**，我们对 unit 一律
> 就地改 12 字节（§9.4），保持 stock 尺寸不变。

### 决定性数据

```
unit 节点 #24:  hash=1464994495  attach_muzzle  parent=15(boss)  pos=[0.0, 2.34, 0.125]
```

`1464994495` 就是 `attach_muzzle` 的全局名字哈希 —— 与 LAS-5 Scythe 的 #16 节点**完全相同**。
位置 `Y=2.34`（Scythe 是 `0.466`）正是这个 mod 所谓的"加长"：**把发射点沿枪管方向前移 2.34 米**。

### 结论

1. **发射点位置在资源侧、由 `attach_muzzle` 节点的 transform 决定** —— 这不再是我们从格式推出来的推断，
   而是有一个已发布的公开 mod 在用同样的字段做同样的事；
2. 该 mod 同时替换 bones 和 state_machine，说明"武器外观/动作/发射点"是一组可协同修改的资源；
3. 与我们自己的 `patch_3`（Scythe attach_muzzle +1.5 m）**用的是同一个字段、同一个偏移算法**。

---

## 11. 实机验证（2026-10-21 18:50，build 25988413）

一次启动同时验了三件事。

### 11.1 发射点由 unit 资源的 `attach_muzzle` 节点决定 ✓

补丁：`mods-spike/scythe_muzzle/build/…patch_3`（LAS-5 Scythe，`attach_muzzle` 的 Y 从 0.466 改到 1.966）。

| 观察 | 结论 |
|---|---|
| 发射点出现在**枪管前方** 1.5 米 | 节点 transform 直接决定发射点 |
| **枪口模型也一起前移** | 该处顶点蒙皮（skinning）绑定在这个节点上 |

**轴向纠正**：武器的局部坐标里 **Y = 枪管朝前**，不是向上。这也解释了"热熔加长"把 Y 从 0.466 拉到 2.34 的含义（沿枪管前移 2.34 m）。

**推论（⚠ 未单独验证）**：移动节点会连带移动"绑定在该节点上的顶点"。因此可以在不改几何的前提下，
移动/旋转武器的某个部件（枪口、握把、弹匣口）。"热熔加长"额外替换了 gpu（11.3 MB 网格），
是因为它要的是**更长的枪管几何**，而不是把已有末端挪走。

### 11.2 纯 Lua HUD ✓

```
RESULT: YES - a screen gui was created and Gui.text returned id number:0
S9 frame 1 … 7200  draw#1 … #7200  pcall_ok=true  is_visible=true
```

`World.create_screen_gui` → `Gui.set_visible` → `Gui.has_all_glyphs` → `Gui.text_extents`
→ `Gui.text(..., "core/performance_hud/debug", 64, "core/performance_hud/debug", Vector2, Color)`
全链路通过，**每帧重画 7200 帧不崩**，immediate 模式正确（对象不累积）。
⚠ 屏幕像素是否可见待用户确认（主菜单 world 未必在渲染）。

### 11.3 引擎插件系统可被 Lua 驱动（部分）✓

```
PluginManager.loaded_plugins() → havok_physics, level_generation, wwise_plugin   (3 个)
PluginManager.load_plugin("dsh_missing_probe")        → pcall_ok=true, 无返回值（静默 no-op）
PluginManager.load_relative_plugin("dsh_missing_probe") → 同上
```

两个要点：
1. 实际加载 **3 个插件**，比 `bin/plugins` 目录里看到的 2 个多一个 `havok_physics`（另有加载来源）；
2. **`load_plugin` 对不存在的名字不报错、不返回值** ⇒ 下一版测真实 DLL 必须用
   `loaded_plugins()` 调用前后**差集**判定，不能靠错误文本。

### 11.4 本轮确认的能力边界（更新）

| 能力 | 状态 |
|---|---|
| 任意资源类型替换（`.patch_N`） | ✓ 实测（physics / unit） |
| 发射点位置（unit 节点 transform） | ✓ 实测 |
| 绑定顶点随节点移动 | ✓ 实测（枪口模型随之前移） |
| 纯 Lua 屏幕 GUI + 逐帧文本 | ✓ 实测（调用层） |
| 引擎插件系统可枚举/可调用 | ✓ 部分（静默失败，需差集判定） |
| 动画 / 状态机资源 | 明文可替换（codec 未写） |
| 玩法数值（伤害/弹匣/护甲） | 未通（组件表 / 加密 dl_bin） |

---

## 12. 第二个玩法级案例：Weakpoint Lock-On All-In-One 3.0

分发包 `D:\Downloads\Weakpoint_LockOn_All_In_One_3.0.zip`（2026-10-21），归档分析于 `C:\Users\Admin\AppData\Local\Temp\lockon`。

### 12.1 结构

17 个可勾选选项，每个选项 = 一个按敌人拆分的补丁目录（`Mods/<敌人>/<部位>/…patch_0`）。
每个补丁替换该敌人的 **`bones`** 资源，多数还带 `ragdoll_profile` / `unit` / `state_machine`。

样本：

| 敌人/部位 | 条目 | bones 大小 | 骨骼数 |
|---|---|---:|---:|
| Berserker | bones + ragdoll_profile + unit | 1,106 B | 65 |
| Charger/Head | 10 entries | 1,006 B | 58 |
| Commander/Head | 7 entries | 1,166 B | 65 |

### 12.2 机制（从 bones 解码看）

Berserker 的 65 根骨骼里与瞄准/锁定相关的是：

```
#9  chest_aim                           #10 head
#15 head_aim                            #18 grp_head_local_orientation
#19 loc_aim_override_local_orientation   #32 r_aim_weapon   #33 l_aim_weapon
```

README 说明"数字越大，锁定点越往里"（Titan 的 1/2/3 选项）。结合 bones 的格式
（`hash[i]` 与 `names[i]` 按索引一一对应），机制应为：

> **锁定系统按名字（哈希）查一根骨骼；改 bones 资源里的"哪个索引挂这个哈希"，
> 就等于把锁定点搬到另一根骨骼的位置。**

⇒ **敌方锁定点/弱点位置也是资源侧的**，而且只需要改几百字节的 bones 资源。

### 12.3 与发射点案例的关系

两者是同一套机制的两个方向：

| | 谁被改 | 改什么 | 效果 |
|---|---|---|---|
| LAS-5 Scythe / 热熔加长 | 玩家武器的 unit | `attach_muzzle` 节点 position | 发射点前移 |
| Weakpoint Lock-On | 敌人的 bones | 名字哈希↔索引的对应 | 锁定点搬到另一根骨骼 |

两条都不需要 Lua、不需要内存、不需要 loader —— 纯 `.patch_N`。

## 13. HUD 实机结果：调用成功但**不可见** —— **已解决，是模式错了**

```
Gui.text(...) → 返回 id 0；每帧重画 7200 帧 pcall_ok=true；is_visible=true
屏幕：什么都没有
```

判定：**调用层通了，渲染层没通**。

> **结案（2026-10-21 19:53，0.5.0 实机 A/B）**：真因是**用了 immediate 模式**。这个 build 的
> immediate 图元调用全部成功、`is_visible` 回报 true，但**不被合成器绘制**。换成 **retained 模式**
> （`create_screen_gui(world,"scale",1,1)`，画一次存 id，`set_visible(gui,id,true)`）后
> **`DSH RETAINED` / `DSH LINE2` 直接出现在屏幕上**，21,600 帧稳定。
> 字体、材质、坐标、world 都没问题；`_G.render` 也从没被引擎调用过（0.4.0 已证）。
> 详见 [GUI-HUD-25988413.md](GUI-HUD-25988413.md) §7。

原先怀疑的两个原因（都已被证否/无关）：

1. ~~**immediate 模式的图元必须在该世界的 `render` 阶段绘制**~~ —— 挂 `render` 也没用，
   `_G.render` 引擎根本不调用（0.4.0 实测）。
2. ~~主菜单的 `main_world()` 未必是被渲染的那个 world~~ —— 同一个 world 的 **retained** gui 画得出来。

~~下一步（exp_hud 0.4.0）：把绘制从 `update` 挪到 `render` 回调里~~ —— 0.4.0 做了，`_G.render` 存在
但引擎从不调用，只在日志里留了 `[draw] phase=U`。这条路是死的，正确解法是换 retained 模式。

---

## 14. `state_machine` 资源里到底有什么（2026-10-21 19:2x）

样本：热熔加长 `0x6CFCC7F8801A0266`（1,452 B，熵 2.445）／Crusher `0x905809A4C28D8A45`（50,636 B，熵 3.066）。
无 srkit codec（raw），但结构是明文，可以直接读。

### 14.1 头部：计数 + 段偏移表

```
+0x00 u32 states?        热熔=1     Crusher=0x0F(15)
+0x04 u32 transitions?   热熔=2     Crusher=0x14(20)
+0x08 u32 0x50（疑似头长/版本）
+0x0C u32 0x07 / 0x7C     ← 段偏移
+0x10 u32 0x514 / 0xBAE0  ← 段偏移
+0x14 u32 0 / 7           ← 该段计数
+0x18 u32 0x530 / 0xBCD0  ← 段偏移
+0x1C u32 4 / 9           ← 该段计数
+0x20 u32 0x538 / 0xBD08  ← 段偏移
```

模式是「偏移, 计数」成对的段表，与 Stingray 其它资源一致。

### 14.2 段内容（热熔样本实测）

**① 0x514：7 个 32 位哈希**

```
0x69AFD8B1  0xA4DD22E8  0xC05E089F  0xDA4412E3  0xE62AFEFC  0xF19FFE15  0xF5EACFD8
```

= **动画/状态的名字哈希**（IdString32，和骨骼名同一套 murmur64 高 32 位）。
⇒ 状态机靠哈希引用动画资源，和 bones 引用骨骼名的机制完全同源。

**② 0x530 / 0x538：浮点参数块**

```
@0x530:  ... 1.0   -9.8   1.0   0.5
@0x538:  ... 1.0   -9.8   1.0   0.5   0.087
```

`-9.8`（重力）、`1.0`（速度/权重）、`0.5`（混合时间）、`0.087`（时长/阻尼一类）
⇒ 这是**运动/混合参数**，纯 float32，可按偏移就地改。

### 14.3 由此得到的三种改法

| 改法 | 可行性 | 说明 |
|---|---|---|
| 整份替换 | ✓ 已有多例（热熔加长、Weakpoint） | 纯 `.patch_N` |
| 换引用（哈希表） | ⚠ 待验 | 像 bones 那样把某个哈希换成另一段动画的哈希 |
| 改浮点参数 | ⚠ 待验 | 混合时间/速度/重力，按偏移就地改（同 unit transform 的做法）|

### 14.4 与发射点实验的呼应

`attach_muzzle` 只改视觉与特效起点、不改命中（§11.1 实机：抬 1.5 m 后激光仍命中准星所指）。
而状态机管的是**动作怎么播**（含火焰持续/喷发节奏这类）——两者配合才是完整的"武器表现"改造。

### 14.5 那个 `-9.8` 是谁的？（2026-10-21 19:3x）

全量搜索 `-9.8`（0xC11CCCCD）在这几个资源里的出现：

```
热熔加长 state_machine (1,452 B)   → 2 次，偏移 0x544 与 0x57C
    两处邻域完全相同：[0,0,0, 1.0, -9.8, 1.0, 0.5, 0.087, 0]
Crusher state_machine (50,636 B)   → 0 次
热熔加长 unit (12,808 B)           → 0 次
Berserker bones (1,106 B)          → 0 次
```

对照该武器的 bones 列表：`hose_jiggle_01` / `hose_jiggle_02` —— **正好两根软管骨骼**，
而 -9.8 也正好出现 **两次**，每处是一个 9 浮点的"运动参数块"（速度/重力/权重/混合/时长）。

⇒ ⚠ 高置信推断：**这个 -9.8 是软管骨链的 jiggle 重力**，不是弹道重力。
改它只会让软管晃动得更狠/更飘，不会改变弹丸轨迹。

### 14.6 弹道重力在资源侧有没有入口？

**没有。** 依据：
- `state_machine` = 动作层（本节已证：只有软管/动作参数）；
- `unit` = 视觉节点层（§11 已证：只改视觉起点，不改命中）；
- `physics` = Havok 刚体（载具/道具/植被），不是子弹；
- 弹丸行为在 **组件数据**（ProjectileComponentData 一类）→ 落在加密的
  `data/game/generated_projectile_settings.dl_bin` / `generated_entities.dl_bin`（§7：熵 8.0、非资源、不可 patch）。

⇒ 想改"实际弹道/伤害"，只有两条路：**解开 dl_bin 加密**，或拿到**能在进程内跑的代码**（签名插件 / crashpad 全量 dump 之后离线改）。

---

## 15. `physics` 资源覆盖的对象范围（2026-10-21 19:2x）

`srkit list --type physics` 全量 39,016 条，其中 21,731 条带可解析名字。按关键词筛：

| 类别 | 例子（physics 资源名） |
|---|---|
| 手榴弹 | `grenade_40mm_frag`、`emp_grenade/emp_grenade`、`conscript_grenade_he`、GL-21、GP-31 |
| 燃料罐 | `flamethrower_canister` |
| 补给/舱体 | `hellpod/hellpod`、`hellpod_l`、`hellpod/ammo_rack`、`hellbomb` |
| 信标 | `locator_beacon` |
| 背包 | `AX/AR-23`、`AX/ARC-3`、`AX/FLAM-75`、`K-2` |
| 地雷 | `mine_launcher`、`cy_sat_minefield_16m_01…` |
| 机炮吊舱 | `eagle_gun_pods`、`eagle_rocket_pods` |

⇒ **投掷物/补给舱/背包/地雷确实有 Havok 刚体资源**，与 FRV 同一类型（`0x5F7203C8F280DAB8`）。

### 15.1 能改什么、不能改什么

| 参数 | 在哪 | 能否资源侧改 |
|---|---|---|
| **质量（kg）** | physics：`0x4A182741` + flags + f32（§17）| ✓ **已钉死**，社区同槽位实机验证过 |
| 惯性张量 / 重心 / 体积 | physics（1,725 份带这些字段名）| ✓ 存在，字段偏移待定位 |
| 摩擦 / 弹性 / 阻尼 / 重力因子 | **不在** physics（2,453 份逐份搜字段名，0 命中）| ✗ 属组件数据层 |
| 重力（全局） | 物理世界设置（不是 per-body）| ✗ |
| 弹丸初速/引信/伤害 | 组件数据 → 加密 dl_bin | ✗ |

### 15.2 工具瓶颈 —— 已解决（见 §16）

原先 `srkit extract --id` 每条要全库扫描（>10 分钟），`resource_fetch.py index` 也慢到不可用。
根因是 **纯 Python LZ4 解码器**（43 MB/s）扛 6.7 GB 的 toc，不是搜索本身。
给 `srkit.util.lz4block.decompress` 接上 C 扩展后全量索引 **8 秒**建完，62,915 个 id 任意取。
详见 §16。

---

## 16. 全量资源索引（2026-10-21 19:35）

### 16.1 根因：不是搜索慢，是 LZ4 解码慢

`resource_fetch.py index` 老版本对每个 toc 包调 `Repository.load_package`，
而 `srkit/util/lz4block.py` 是**纯 Python LZ4 块解码器**。实测同一批真实 chunk：

| 解码器 | 吞吐 | 6,753 MB toc 推算 |
|---|---|---|
| 纯 Python（原实现） | 43 MB/s | ~156 s |
| `lz4.block`（C 扩展，本机已装 4.4.5） | **3,440 MB/s** | ~2 s |

⇒ ✓实测 快 **79 倍**。

修复：`lz4block.decompress()` 优先走 C 扩展；C 解码器比我们的实现**更严格**（强制
LZ4 规范"末尾 5 字节必须是字面量"），所以**拒绝时回退纯 Python**，语义零变化：
纯 Python 能读的块永远能读，只有速度不同。`SRKIT_LZ4_PURE=1` 可强制走慢路径（自检用）。
压缩仍走纯 Python —— 保证重打包字节可复现。

验证：80 个真实 chunk 两条路径输出**逐字节相同**；`tests/selftest.py lz4` 两条路径都通过。

### 16.2 索引规模与耗时

`D:\mod\tools\resource_index_build.py`（新）→ `D:\mod\cache\resource_index.pkl`（6.0 MB）：

```
3,522 个 toc 包 / 6,753 MB / 62,915 个 id / 322,810 个条目 / 47 种类型 / 0 错误
```

只读 **toc** 包：`gpu_resources` 46.8 GB、`stream` 112.7 GB 一个字节都不碰（条目表只在 toc 里）。

### 16.3 能并行吗？—— 进程可以，线程不行（✓实测）

同一份数据、四种跑法，输出完全一致（62,915 ids / 322,810 entries）：

| 模式 | 耗时 | 相对串行 |
|---|---|---|
| 串行（冷 / 热） | 14.4 s / 14.0 s | 1.00× |
| **20 线程** | **16.4 s** | **0.85×（更慢）** |
| 18 进程 | 7.8 s | 1.79× |
| **6 进程** | **6.2 s** | **2.26×（最优）** |

结论：
- **线程无益反而有害。** 解压本身已经放开了 GIL，但包重组（`data[a:b] = chunk`
  的逐 fragment 拷贝 + `Package.parse`）全在 GIL 下，线程只是加点切换开销。
- **进程线性有效**，但**超过 ~6 个反而退化**（18 进程 8.0 s > 6 进程 6.2 s）：
  每个 worker 要独立 mmap + 解 `bundles.nxa` 索引 + spawn 启动，到 1 GB/s 量级后
  瓶颈转移到磁盘/内存带宽，再加 worker 只增加争用。
- 任务本身**天然可切分**：3,522 个 toc 包彼此独立，切 8 个一 batch（440 batch）动态派发。

### 16.4 一个 id 对应多种类型（重要语义）

Stingray 里 **id = murmur64(资源路径)**，同一条路径会产出多个类型的资源：

```
0xcc21c7ffd3ebefb9  (divers/vehicles/frv/frv)
  units   2 条 / bones 3 条 / physics 2 条 / state_machine 3 条
```

⇒ **只凭 id 取资源是歧义的**。`resource_fetch.py get` 现在会列出候选类型要求 `-t`，
`--all` 可一次导出全部类型。这条以前被 `candidates[0]` 掩盖（FRV 的 physics 请求
悄悄拿到了 bones）。

### 16.5 交叉验证（✓实测，7 个已知样本）

| id | 类型 | 索引读出 | 文档记录 |
|---|---|---|---|
| `0xcc21c7ffd3ebefb9` | physics (FRV) | 264,208 B | 264,208 B ✓ |
| `0x9b2140378640432e` | physics (frv_supply) | 307,504 B | 307,504 B ✓ |
| `0x2d85bfe3d8717fe5` | physics (frv_flamer) | 282,064 B | 282,064 B ✓ |
| `0x6cfcc7f8801a0266` | bones (热熔) | 236 B | 236 B ✓ |
| `0x6cfcc7f8801a0266` | state_machine | 1,452 B | 1,452 B ✓ |
| `0x905809a4c28d8a45` | state_machine (Crusher) | 50,644 B | 50,636 B（补丁口径，差 8 B）|
| `0x27ee1ed8f6fb6356` | unit (Scythe) | 13,344 B | — |

Scythe unit 与我们上一版就地改过 z 的副本对比：**只有 4 字节不同**（`0x59C..0x59F`，即 pos.z
一个 float），stock `pos=(-0.0001, 0.4658, 0.1188)` → 改后 `1.6188`。⇒ 就地改 12 字节的
方案与 stock 完全同源，只动了目标字段。

### 16.6 解锁：命名的物理资源目录

把索引 id 与 `hashlists/hashlist-normalized.csv`（`bits=64` 的 4,739 条）join：

- 索引用 62,915 个 id 中 **3,606 个有名**（5.7%）
- physics 资源 4,839 个 id 中 **2,453 个有名** → 已写入 `D:\mod\cache\physics_named.txt`

手雷**每一颗都有独立 physics 资源**（都可按 id 取，✓实测）：

```
0x7686544f539bb9b7  G-16 Impact          2,876 B
0x6b11fc757618c57e  G-12 High Explosive  8,892 B
0x0080869506299773  G-23 Stun
0xc5c05fcb5747c799  G-123 Thermite
0x04653ab33f3ffb44  G-10 Incendiary
0xdb922a7afc42894b  G-31 Arc
0x2d398d1ec35e0838  G-50 Seeker
0x3fa94f58f596bc0b  G-109 Urchin
0x03f31caf3a7d8f4e  G-142 Pyrotech
0xeb725c39fc38b87c  G-13 Incendiary Impact
```

舱体/补给：`hellpod 0x583ecde0d7718126`(17,212 B)、`ammo_rack 0x5052ec6a928ccf1a`(102,732 B)、
`hellpod_lid`、`hellbomb`、`landingzone_beacon`、`aa_turret`、`manned_turret`。

四个资源头部一致（`b8 da 80 f2 c8 03 72 5f` = physics 类型 id，紧跟 id 低 32 位），
熵 5.0–5.7 —— 与 FRV 同族，只是体积小两个数量级。

⇒ 下一张多米诺：**质量/摩擦/弹性这些 per-body float 现在有入口了**（§15.1 那行 ⚠ 可以转 ✓）。

### 16.7 用法

```bash
python D:\mod\tools\resource_index_build.py --mode process --workers 6   # 重建（6 s）
python D:\mod\tools\resource_fetch.py stats                              # 类型统计
python D:\mod\tools\resource_fetch.py get <id> -t 0x5F7203C8F280DAB8 -o out.bin
python D:\mod\tools\resource_fetch.py types physics --limit 50           # 列某类型
python D:\mod\tools\resource_fetch.py find cc21                          # 按 id 前缀找
```

### 16.8 physics 载荷的公共头部（新发现）

所有 physics 载荷（FRV 264 KB、G-16 2.9 KB、hellpod、ammo_rack）开头 **16 字节完全同构**：

```
+0x00  u64  type id      = 0x5F7203C8F280DAB8
+0x08  u64  resource id  = 完整 64 位 murmur64
+0x10  u32  size         = 本文件的字节数（自描述长度）
+0x14  12 字节 0
```

例：`G-16` → `type=5f7203c8f280dab8 id=7686544f539bb9b7 size=2876 (file=2876)` ✓
`FRV` → `type=5f7203c8f280dab8 id=cc21c7ffd3ebefb9 size=264208 (file=264208)` ✓

⚠ **但"裸 float32 数组"这个说法要收窄**（订正 §15.1）：

| 资源 | 大小 | 落在 (0.001,2000) 的 float32 |
|---|---|---|
| FRV `frv/frv` | 264,208 B | 9,354 / 66,052 words（14%）|
| G-16 Impact | 2,876 B | 27 / 719 words（3.8%）|

⇒ FRV 那种 264 KB 的载具资源里 float 多到可以逐个试改（社区案例正是这么找到的），
但**小道具（手雷）的资源内部不是一片连续 float**，含量少且夹在二进制结构里。
改质量/摩擦必须**先定位字段偏移**，不能按"数组第 N 个 float"猜。
定位手段：同族资源对拍（G-16 vs G-12 vs G-23）、与 LUA/wiki 数值比对。

`D:\mod\cache\physics\` 已存全部 2,453 个命名 physics 资源（含文件名的 id 前缀），
可直接离线对拍。

---

## 17. 刚体质量字段 —— 钉死了（2026-10-21 19:5x）

### 17.1 字段布局

physics 载荷是 **Havok 2019.01 tagfile**（`TAG0`/`SDKV20190100`/`DATA`/`TBDY`/`TPTR`/`INDX`/`ITEM`/`PTCH`），
类型库以明文内嵌，`hknpShapeMassProperties` → `hkCompressedMassProperties` 的字段名
（`centerOfMass`/`inertia`/`mass`/`volume`）都能读到。但**能用的是下面这个更简单的偏移**：

```
+0x00  u32   0x4A182741        ← 刚体描述符标记（IdString32）
+0x04  u32   flags             例 0x100 / 0x110 / 0x111
+0x08  f32   质量（kg）        ← 可改
+0x0C  7×u32 0xFFFFFFFF        7 个无效 Havok handle
```

标记在**大多数资源里位于 0x78**，载具资源因路径更长位于 0x118 ⇒ **永远按标记搜索，不要写死偏移**。
2,453 份命名物理资源里 **431 份**有该标记；其余是没有刚体描述符的场景物件。

### 17.2 三路互证（✓实测）

| 证据 | 内容 |
|---|---|
| ① 结构一致性 | 431/431 份**全部**满足 `标记 + flags + float + 7×(-1)`，无一例外 |
| ② 数值符合现实 | FRV **3000**、补给 FRV 2500、火焰 FRV 7500、运输机 **10000**、hellpod **35**、hellbomb **10**、MG-206 **15**、SG-225 **5**、G-12 **3**、G-16 **5**、G-50 **0.5** —— 全部是 kg 量级 |
| ③ 社区已实机验证 | 社区 FRV 防翻转 mod 的 README 写明 `Mass: M-102 3990 (3000)`，而我们扫他们补丁得到的值**正是 3990**，位于同一槽位（flags=0x111） |

⇒ ✓ **该 float32 就是刚体质量（kg）**，且社区已证明改它在游戏里生效。

### 17.3 手雷的刚体质量（✓实测，10/10 都有）

| 手雷 | 质量 kg | 手雷 | 质量 kg |
|---|---:|---|---:|
| G-16 Impact | 5.0 | G-12 HE | 3.0 |
| G-10 Incendiary | 5.0 | G-23 Stun | 3.0 |
| G-13 Incendiary Impact | 4.0 | G-31 Arc | 3.0 |
| G-109 Urchin | 5.0 | G-50 Seeker | 0.5 |
| G-123 Thermite | 5.0 | G-142 Pyrotech | 5.0 |

全部位于 `0x78`（同一族），`flags` 多在 `0x110`。

### 17.4 摩擦 / 弹性 —— 资源侧**不存在**（✗ 边界）

2,453 份载荷逐份搜字段名：

```
friction        0 files      restitution   0 files      damping        0 files
hkMaterial      0 files      linearDamping 0 files      angularDamping 0 files
centerOfMass 1725 files      inertia    1725 files      mass 1725 files   volume 1725 files
```

⇒ 资源侧只暴露 **质量 / 惯性张量 / 重心 / 体积**（形状质量属性）。
摩擦、弹性、阻尼、重力因子**不在这 1,725 份里**，属于组件数据层（加密 `dl_bin`）。
这条是**否证**，不是"还没找到"。

### 17.5 测试补丁（已离线造好，未安装）

`D:\mod\mods-spike\grenade_mass\build\9ba626afa44a3aa3.patch_4`（12,048 B，2 条目）：

| id | 手雷 | 质量 |
|---|---|---|
| `0x7686544f539bb9b7` | G-16 Impact | 5.0 → **60.0**（12×） |
| `0x6b11fc757618c57e` | G-12 HE | 3.0 → **0.3**（1/10） |

回归：两个 payload 与 stock **同尺寸**，分别只差 **2 字节 / 4 字节**（就是质量那 4 个字节），
`dump` 回来质量读数 60.0 / 0.3 ✓。

### 17.6 工具

```
D:\mod\tools\physics_probe.py mass [--dir ...] [--filter REGEX] [--top N]   # 全库列质量
D:\mod\tools\physics_probe.py setmass <payload.bin> <kg> [-o out.bin]       # 改单份
```

`D:\mod\cache\physics\` 里 2,453 份命名载荷（文件名带 id 前缀）可直接对拍。

---

## 18. 手雷 mass=0 实验：投掷物**不是** Havok 刚体（2026-10-21 20:1x）

### 18.1 实验

`patch_3` 把 G-16 Impact 的刚体质量 `5.0 → 0.0`（2 字节），实机投掷：

```
y 正常下降、正常落地、正常爆炸 —— 和 stock 完全一样
```

### 18.2 为什么这一局是有信息量的

上一局（mass 60 vs 0.3）无变化**不能**说明问题：自由落体和抛体轨迹本来就跟质量无关。
但 **mass=0 不一样**：Havok 里质量 0 = 无限质量 = 静态/运动学体。如果投掷物由这份 body 驱动，
它应该**冻在半空**或**原地不动**。它照常下落 ⇒ 结论成立。

### 18.3 结论

| 判断 | 依据 |
|---|---|
| ✗ **投掷物运动不由该 physics 资源驱动** | mass=0 本应使刚体静止，实测完全正常 |
| ✗ 资源侧无摩擦/弹性/阻尼 | 2,453 份载荷按字段名搜，0 命中（§17.4）|
| ✗ 质量/惯性/重心对投掷无影响 | mass 60 / 0.3 / 0 三次实测，飞行与落地均无差异 |

⇒ **资源侧改投掷物物理这条路封死**。弹道、初速、重力在加密组件层（`dl_bin`），与 §14 的判断一致。
物理资源能改的只有**载具/道具这类真刚体**（FRV 案例就是这一类）。

残留不确定性（⚠ 未排除）：这个 build 里 physics 类补丁是否 100% 生效，我们没用自己补丁验过
（社区 FRV mod 是第三方证据）。若要钉死，最省事的一发是把 **FRV 质量改 0**，看车会不会卡死。

### 18.4 顺手拿到的两件东西

1. **HUD 能当量具用了**：FPS 无关的 `updates/fails` 计数、世界时间 `t`、`dt`、单位总数 `units`
   全部实时显示（`updates=594 fails=0`）。
2. **Lua 能读世界**：`World.num_units` / `World.units` / `Unit.world_position` /
   `Vector3.element` 在任务世界里全部可用（`units=13734`、`t=253.08`）。

### 18.5 HUD 自己的两个 bug（0.7.0 修）

| bug | 现象 | 修法 |
|---|---|---|
| 扫描被 cap 截断 | 任务里 `num_units≈3554`，只扫前 1200 个 | 去掉 cap，全量扫，降到每 60 帧一次并显示耗时 |
| 按名字子串认人 | 资源名是 `IdString64 #ID[hex]`，没有可读路径 ⇒ 永远 0 命中 | 改成按**资源 id hex** 匹配（同一路径多类型共用 murmur64）|

### 18.6 崩机：0.7.0 全量遍历 `World.units()`

**现象**：启动 60 s（frame=3600，主菜单 `units=1`），世界加载后立刻崩溃。无 minidump、无事件日志，
`ExpHud.log` 停在 frame=3600 的 C4 心跳，之后一行都没有。

**根因**：0.7.0 的 `scan_all()` 对 `World.units()` 的快照做**全量遍历**（任务世界 3,554 个单位）
并逐个调 getter，还新增了两个本会话从未跑过的调用 `Unit.world_position` / `Unit.has_camera`。

这**正好违反 2026-10-20 21:44 就已记录的纪律**（`docs/STINGRAY-API-25988413.md`）：

> 转储里的故障指令 `movsd xmm0, qword ptr [rdi + rbx + 0x30]`，`rdi = index<<6` → **越界读**
> ⇒ `world:units()` 返回的是快照，活世界里句柄随时失效。
> **不允许 `for` 一遍列表再逐个调 getter —— 拿到就立刻用、而且只用极少数几个。**

**为什么 0.6.1 活着而 0.7.0 死了**：

| 版本 | 遍历范围 | 每个单位调什么 | 结果 |
|---|---|---|---|
| 0.6.1 | `min(1200, N)`，每 30 帧 | 只调 `resource_name` | 活了 17,850 帧 |
| 0.7.0 | **全部 3,554**，每 60 帧 | `resource_name` + 匹配后 `world_position`，另加 600 次 `has_camera` | 世界加载后立刻崩 |

**修法（0.7.1）**：撤掉一切句柄遍历，只保留**世界级零参读取**（`num_units` / `time` / `delta_time`），
`Unit` / `Camera` 一个句柄都不碰。

**教训（补进纪律）**：
1. 纪律写在文档里 ≠ 写进了下一版代码。**新探针必须先对照 `docs/` 里同名 API 的事故记录**再动手。
2. `pcall` 拦不住这类崩溃 —— 引擎侧越界是进程级死亡，不是 Lua 报错。唯一防线是**不碰**。
3. 崩溃无产物时，判据是**时间相关性 + 代码路径对照**：崩溃点正好在世界加载、正好是两条从未执行过的新路径。

#### 18.6.1 修复验证（✓ 2026-10-21 20:40–20:46 实机）

`exp_hud 0.7.1`（6,848 B，md5 `2bd7f114…`，零句柄遍历）实机跑通：

```
C5 frame=8100  units=1      t=41.9    updates=270  fails=0     主菜单
C5 frame=9000  units=3552   t=49.4                          世界加载
C5 frame=11700 units=13635  t=95.0                          任务世界
C5 frame=25200 units=13715  t=342.1   updates=840  fails=0   6 分钟无崩溃
```

⇒ ✓ **崩机修掉**（25,200 帧 / 840 次文本刷新 / 0 失败），
⇒ ✓ 世界级读数稳定（`num_units` / `time` / `delta_time`），
⇒ ★ **关键数字：任务世界有 13,700 个单位**（此前文档记的 6,610 是另一个任务/更早的 build 状态）。
这个数量级正是 0.7.0 必死的量化解释：全量遍历 13,700 个快照句柄，撞上失效句柄几乎必然。

**结论已进闸**：`tools/check_unit_snapshot.py` 把"`units()` 循环里调 `Unit.*`"变成构建期 FAIL。
