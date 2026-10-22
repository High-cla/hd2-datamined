# 两个社区 mod 与我们的路线：它们在路上吗？能共存吗？

对象：
* **SHODAN-Stat-Editor v3.0.0 "Offline"（SSEO）** —— 2026-10-22 更新，856 KB 的离线程序
* **护甲多被动**（`D:\Downloads\护甲多被动.zip`，今早那份）

## 1. 它们分别在哪条路上

### SSEO v3.0.0 = 我们路线里的"**直接改表文件**"子路线

Release 说明原话：*"game build 25988413 removed what the in-game panel needed, so the Stat Editor is
now a Windows program that writes your values into the game's own data files. No mod loader, and the
game does not need to run while you edit."*

拆开它的 zip 看，证据齐了：

| 文件 | 说明 |
|---|---|
| `libsodium.dll` | 解/封 `.dl_bin` 的密封盒（和我们 `dlbin_seal.py` 同一件事） |
| `shodan_hash.dll` | 重算内容哈希 —— 就是那道 MurmurHash64A 闸门 |
| `app/install.lua` | 直接 `io.open(..., "wb")` 写 `<game>/data/game/generated_*.dl_bin`；自带 `Offline/originals/*.dl_bin` 备份 + 一份"哪些文件是我写的"哈希清单 |
| 游戏运行时拒绝写 | `if M.game_running() then return nil, 'Helldivers 2 is running: close it first.'` |

**它不写 `patch_N`**，写的是 `data/game` 里的基线表文件。也就是说：
**它和我们 `stratagem_tune.py` 这类改表工具是同一个子路线，和我们的 `patch_0` 那套不是一条路。**

### 护甲多被动 = **不在我们这条路上**（它是 boot/Lua 路线）

zip 里只有一个补丁：

```
data/9ba626afa44a3aa3.patch_0        418,176 B   1 个条目
  entry0: file_id=0xF476DF93691895FA (boot)  type=lua  417,971 B，内容头是 `local PASSIVES =`
data/...patch_0.gpu_resources / .stream   都是 0 B
Recovery/profiles/000.dl_bin          4,064 B = 原版 sealed 的 generated_customization_passive_bonuses（4,016 + 48）
Recovery/profiles.json                9,809 B
Source/boot.lua                       417,963 B（就是那个 patch 里的 lua 源码）
manifest.json                         "占用 boot"
```

`0xF476DF93691895FA` 就是 BSL 用来拿执行权的那个 `boot` 资源。所以它是**运行期 Lua mod**：
靠 loader 执行 418 KB 的脚本，在游戏里改被动 —— 不是改数据表。zip 里那份 `Recovery` 是被动表的
**原版备份**，说明它预期自己会（或曾经会）替换这张表。

**在当前 build 上它跑不起来**：`ffi` 没了，BSL 没有能用的版本，而它的全部逻辑都在 boot lua 里。

## 2. 共存矩阵

| 组合 | 能否共存 | 依据 |
|---|---|---|
| 我们的多个 `patch_N` mod | ✅ | 用 `tools/patch_compose.py` 合成一个 `patch_0`，链上不留空洞 |
| 我们的 `patch_N`（资源型：贴图/网格/lua/骨骼） × SSEO | ✅ 互不影响 | 两个命名空间：SSEO 写 `data/game/*.dl_bin` 表文件，我们写包里被覆盖的资源 |
| **我们的改表**（`stratagem_tune` 之类的输出） × **SSEO** | ⚠ **同一条子路线，会互相覆盖** | 两者都写 `data/game/generated_*.dl_bin`，后写的赢；更麻烦的是 SSEO 的还原基线会漂：见 §3 |
| 我们的 `patch_N` × 护甲多被动 | ❌ | 两者都抢 `patch_0`（护甲多被动靠它装 boot）；我们合成补丁会盖掉它的 boot，反过来它装上来也会盖掉我们的 `patch_0` |
| SSEO × 护甲多被动 | 数据上不冲突 | 一个改表文件、一个占 `patch_0` 装 boot；但护甲多被动本身跑不起来 |

## 3. SSEO 的"还原"会踩到我们（这条要看懂）

`install.lua` 的归属判定（原文摘要）：

```
if current and list[name] and list[name][hash_of(current)] then
    -- 这个文件的当前哈希在我们写过的清单里 -> 它是我们的，original 用保留的那份
elseif current then
    -- 否则：把当前文件当作"原版"，并删掉之前保留的同名 original（认为游戏更新过）
end
```

意思是：**SSEO 只认自己写过的文件**。如果我们的工具先改了一张表，SSEO 会把你改过的那份
当成"原版"存进 `originals/`。之后你按 **Restore the game's files**，还原出来的是**我们的改动版**，
不是原版 —— 而且它会认为自己写过的文件仍有 original 可回，容易形成"越还原越乱"。

⇒ 两条子路线**不要交替使用同一张表**。要用，二选一：
* 只用 SSEO 改表；我们的工具只做只读分析与 patch 资源；
* 或者把 SSEO 的修改结果**收编**成我们的补丁（改完表 → 读出改后的表 → `patch_compose` 打成 `patch_0`
  → 用 SSEO 的 Restore 把基线还原回去），这样链上只有一条，可复现、可合并、可回滚。

## 4. 结论

1. **SSEO 符合我们路线的核心纪律**（保哈希、先备份、游戏运行时不写），但它走的是"改基线文件"
   子路线，不参与 `patch_N` 链 —— 所以它不需要遵守"序号连续"，也不会破坏我们的链。
2. **护甲多被动不是我们这条路线的 mod**，是 boot/Lua 路线，占 `patch_0` 且当前 build 不可用。
3. 真正要小心的是**表文件级冲突**：我们和 SSEO 改同一张表时，只有后写的生效，而 SSEO 的
   还原会把我方改动误当原版。要长期共存，必须收敛成一条链（收编进补丁）。

## 5. 下一步建议

* 要做"我们 + SSEO"的共存：先定一张**互不重叠的表清单**（我们改战备表，它改武器/弹丸/护甲被动表），
  两边各改各的；这需要先读出 SSEO 到底写哪几个 `generated_*.dl_bin`（它的 `originals/` 目录会列出来，
  但那要真装一次）。
* 要做"我们 + 护甲多被动"：需要能执行 Lua 的 loader（当前没有），或者把它的效果翻译成表修改
  （它的 `Source/boot.lua` 是明文，可读，逻辑是"给被动加 stat 行"那种），这属于新的逆向工作。

## 6. 为什么 SSEO 与"护甲多被动"不能共存（拆开 boot.lua 后定案）

护甲多被动**不是**运行时改内存的 mod，它做的和我们一模一样 —— 直接改表文件。它的 `Source/boot.lua`
里写得很清楚（原文节选）：

```lua
local target = "data/game/generated_customization_passive_bonuses.dl_bin"
local backup = "ArmoryForge-Multi.original.dl_bin"
local applied_path = "ArmoryForge-Multi.applied.dl_bin"
...
if #list == 0 then
    desired = ORIGINAL_SEALED
else
    local ok, plain = pcall(merger.build, ORIGINAL_PLAINTEXT, list)   -- 从【内嵌原版明文】重建
    local ok2, boxed = pcall(sealer.seal, plain)                      -- 自己重封装
```

它还内嵌了 MurmurHash64A + 校正字求解器（`local murmur = (function() ...`）、`ORIGINAL_PLAINTEXT`
（原版明文）与 `ORIGINAL_SEALED`（原版封包），以及 `merger` / `sealer`。

**冲突原因一句话：两个 mod 都独占同一个文件，而且各自只认自己的"原版"基线。**

| 谁 | 写什么 | 基线从哪来 | 后果 |
|---|---|---|---|
| 护甲多被动 | `data/game/generated_customization_passive_bonuses.dl_bin` | **内嵌的** `ORIGINAL_PLAINTEXT`（构建时写死的原版），**从不读盘上当前文件** | 它一应用，盘上任何第三方改动（SSEO 的被动数值）**被整体重建覆盖**；取消选择时写回 `ORIGINAL_SEALED`，等于把文件打回原版 |
| SSEO | 同一批 `generated_*.dl_bin` | `Offline/originals/`（只认自己写过的哈希） | 它会把护甲多被动改过的文件**当成原版**存起来，之后 Restore 还原出的是对方的版本 |

所以这是**基线所有权冲突**，不是"加载顺序"问题。谁最后写谁赢，而任何一方的"还原/取消"都会把另一方抹掉。
**这也解释了为什么写一个运行时加载器没用** —— 护甲多被动自己就靠覆盖 `boot` 拿到了执行权，
它缺的不是加载，是"和另一个 writer 共享同一个文件"的机制。

### 6.1 要让它们共存，只有两条路（都不需要 loader）

**A. 换基线（一次性，最省事）**
把护甲多被动 `boot.lua` 里那段 `ORIGINAL_PLAINTEXT` 替换成"已经含 SSEO 改动"的表明文，重新打成
`patch_0`。它启动时就会在 SSEO 的数值基础上再叠被动 —— 两者都在。
代价：绑死一次快照；SSEO 以后重装/改值，得重做这一步。

**B. 单一 owner 的表合成器（推荐，属于我们这条路线）**
让**一个**工具独占那张表：取原版基线 → 应用护甲多被动的 delta（它本质是"给选中被动追加 stat 行"）
→ 再叠加 SSEO 的 delta（它只改数值、不改结构）→ 只封装一次、只写一次、只留一份备份。
我们具备全部零件：`lupa`（真 Lua 5.1，可直接跑它的 `merger.build` 得到合并明文）、
`dlbin_seal.py`（封装）、`murmur64.py`（校正字）、`refs/dlbin/demo/vanilla_*`（原版基线）。
这其实就是把 `patch_compose` 的思路从"资源补丁"扩展到"表 delta"。

**C. 不可行**：写运行时加载器让两者"同时加载" —— 它们不在同一个命名空间里（一个改包内资源靠引擎合并，
一个直接改 `data/game` 文件），没有可以插入的中间层；冲突发生在文件内容层，不在加载层。
