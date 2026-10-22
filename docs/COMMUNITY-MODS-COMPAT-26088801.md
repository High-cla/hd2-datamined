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
