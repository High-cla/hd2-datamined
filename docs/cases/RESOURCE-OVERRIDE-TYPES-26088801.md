# `set_resource_override` 只对 `lua` 有效，还是对所有资源类型都有效？

> build `26088801` · 2026-10-24 · 状态：v1.0.0 **崩在第 2 个类型**（§7.1，已定位到区间）；v1.1.0 逐步版已装，等第二局

## 1. 已知的事实（2026-10-21 三次实机）

`D:\mod\res-override-probe\probe.lua` 1.3.0 / 1.4.0 在 **Lua 5.1 引擎**（build 25988413）上跑出：

| 步骤 | 读数 |
|---|---|
| 对照 | `require("dsh_override_src")` → `no lua resource` |
| 建立 | `set_resource_override("lua", "dsh_override_src", "mods/auto/4")` → `OK returns=0`（3 个参数全是 string） |
| **生效** | `REENTRANT: engine loaded this module AS 'dsh_override_src'` ⇒ **引擎按别名重新加载了资源** |
| 撤销 | `clear_resource_override("lua", alias)` → `OK`，之后又变回 not found |
| 判定 | **`VERDICT: OVERRIDE WORKS`**（`ResourceOverride.log`，21:02 / 21:07 / 21:20 三次一致） |

**只测过 `"lua"`。** 其它类型（`material` / `texture` / `unit` / `bones` …）一次没测 ——
这就是本轮要补的空白。如果它们也通，Lua mod 就能**运行期替换美术/单位资源**，一条 `.patch_N` 都不用写。

## 2. 方法：拿 `can_get` 当跨类型观察口径

`Application.can_get(type, name)` 是布尔预言机。测试步骤（每种类型一遍）：

| 步 | 动作 | 期望（`lua` 已知成立） |
|---|---|---|
| A | `can_get(T, <真实资源名>)` | `true` —— 证明 can_get 认这个类型 + 这个名字是真的 |
| B | `can_get(T, <编造的别名>)` | `false` —— 对照：别名本来不存在 |
| C | `set_resource_override(T, 别名, 真实名)` | 记录 OK / ERR |
| **D** | `can_get(T, 别名)` | **决定性读数**：`true` ⇒ 该类型的 override 被引擎采纳 |
| F | `clear_resource_override(T, 别名)` 后再查 | `false` ⇒ 撤销干净 |

**先用 `lua` 校准这个口径**：如果 lua 的 D 已经是 `true`（我们已知 override 对 lua 有效），
那 can_get **确实会查 override 表** —— 后面别的类型若读到 `false`，才是"这个类型不被采纳"，
而不是"观察方法不灵"。

## 3. 用的三个真实资源名（都经 murmur64 复核）

| 类型 | 名字 | 复核 |
|---|---|---|
| `lua` | `core/wwise/lua/wwise_bank_reference` | 我们 BootProbe 一直能 `require` 成功（实机） |
| `material` | `content/art_shared/base_shaders/nature/terrain_parent_material` | `murmur64 == 0x972691F0D6CAB16B`，与 `hashlists/hashlist-normalized.csv` 一致 ✓ |
| `texture` | `content/env_shared/assets/terrain_materials/textures/generic_bug_acid_displacement.tga` | `murmur64 == 0x90597910CDC70E81` ✓ |

> `unit` 只做"接受性"测试：hash 表里 `units/…` 的条目全是截断名，hash 复核过不了，
> 拿不到可信的真名，所以不能做 D 步（会在 §5 里作为 ⚠ 记下）。

## 4. 预测（开跑前写死）

| 读数 | 判读 |
|---|---|
| `lua`: A=true B=false **D=true** F=false | 口径校准通过（这是前提；不成立则本轮作废） |
| `material` / `texture`: A=true, **D=true** | **override 是类型无关的** ⇒ 运行期资源替换对美术资源成立 ⇒ 打开一条不写文件的新轴 |
| `material` / `texture`: A=true, **D=false**（且 flag 那条也 false） | override 只在 `lua` 生效（或 can_get 不为这些类型查 override 表 —— 两种解释在 §5 里分清） |
| `material` / `texture`: **A=false** | 这个真名在运行时不可见（可能被 bundle 分层/未装载），实验无效，换名字再来 |
| 某个类型出现 `ERR(...)` | `can_get` 不认这个类型字符串，记下 |
| `set_resource_override` 对某类型报 `ERR` | 引擎直接拒绝该类型 ⇒ 也是最强的"不支持"证据 |

另外还会顺带测 `set_resource_override_flag(true)`（因为不确定非 lua 类型是否要开闸）：
序列里如果 D 是 false，会自动再 `set_resource_override_flag(true)` 后重查一次（D2）。

## 5. 已知的解释边界（写在这里免得事后吹过头）

就算 `material` 的 D 读到 `false`，也**不能立刻**断定"引擎不采纳"：
可能是 `can_get` 对非 lua 类型**不查 override 表**（虽然它对 lua 查了）。
两种解释的区分办法（下一轮，若真到这一步）：用一个**真实消费者**去取那个别名的资源
（例如把别名塞给一个会加载 material 的引擎调用），看是否拿到目标。本轮先拿到 can_get 的读数。

## 6. 装了什么 / 怎么读 / 怎么撤

| 项 | 值 |
|---|---|
| 补丁 | `data/9ba626afa44a3aa3.patch_5`（6,329 B toc + 两个 0 B 伴生），资源 `mods/auto/5` = `0xF2EFDB8354D99D1D` |
| 谁执行它 | 我们装的 `patch_0`（BootProbe 1.3.0）扫 `mods/auto/1..6` 时 `require` |
| 日志 | `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\ResOvrTypes.log` |
| 生成器 | `D:\mod\res-ovr-types\resovr_build.py`（`--remove` 一键删） |
| 离线预检 | Lua 5.1 语法 ✓；假引擎（模拟"只有 lua 被承认"）跑通全 30 行日志 ✓ |
| 风险 | 只写一个日志文件；所有引擎调用都 pcall 包裹；失败最多让 BootProbe 记一行 `require FAILED` |

## 7. 结果

### 7.1 v1.0.0（2026-10-24，一局，**崩溃**）

| 项 | 读数 |
|---|---|
| 类型串总览 | 16 个类型串 `can_get` 全部**安全返回 false**（没有 ERR、没崩） |
| `lua` 段 | A=true · B=false · **D=true** · F=false —— **完整跑完并落盘** |
| `material` 段 | **一行都没有** ⇒ 进程在 material 段里死掉，且死在第一次 flush 之前 |
| BootProbe 侧 | 它自己的日志停在 `mods/auto/4`，说明崩在 `require("mods/auto/5")` 里 ⇒ **确认是我们的探针** |
| 结论 1（重要） | **观察口径成立**：`can_get(type,name)` 确实会查 `set_resource_override` 表（lua 的 D 从 false 翻到 true） |
| 结论 2 | `can_get` 对 `material`/`texture`/`unit`/`physics`/… 这些类型串**只读查询是安全的**（总览那 16 行都返回了） |
| 未定 | material 段里哪一次调用致命 —— v1.0.0 把一个 case 的全部行攒到最后才 flush，所以 A/B/C/D 全丢 |

**嫌疑排序**：`set_resource_override("material", …)` 最可疑（10-21 的记录已经证明这个绑定**不校验参数**：
1.0.0 时代传 0 个参数直接崩在 nil 解引用上）。次嫌：`can_get("material", <真实材质名>)` 真取到了材质、
在 boot 早期触碰了图形侧。

**排除**：文件/补丁本身没坏（`srkit check` 通过），也不是 `can_get` 的类型串问题（总览全过）。

### 7.2 v1.1.0（逐步版，已装）

修的就是定位问题：**每次调用前先写 `>>> BEFORE <调用>` 并 close**，所以硬崩之下的最后一行就是凶手。
调用顺序把 4 个**只读**探针排在最前，第一次写探针排在后面 —— 即使写探针崩了，也只读结果仍然拿得到。

| 序 | 调用 | 作用 |
|---|---|---|
| 0 | lua 全套（5 次调用） | 复验口径（已知安全） |
| 1 | `can_get(material, REAL)` / `(material, ALIAS)` / `(texture, REAL)` / `(texture, ALIAS)` | **只读**：真实材质/贴图在运行时可见吗 |
| 2 | **`set_resource_override(material, …)`** | 头号嫌疑，单独成段 |
| 3 | `set_resource_override(texture, …)` | 若上一步没死才继续 |
| 4 | `set_resource_override("dsh_not_a_type", …)` | 非法类型串对照 |

**判读**：日志最后一行是哪个 `>>> BEFORE`，凶手就是它；它上面的所有 `<<< AFTER` 都是已证明安全的调用。

| 最后一行 | 结论 |
|---|---|
| `>>> BEFORE set_resource_override(material, …)` | 写探针致命 ⇒ **非 lua 类型不允许建立覆盖**（最强的"不支持"证据） |
| `>>> BEFORE can_get(material, REAL)` | 读真实材质致命 ⇒ boot 早期材质子系统未就绪 ⇒ 需要**延迟到进任务后**再试（我们已知的 30 s–1 min 教训） |
| `===== … end` | 没崩 ⇒ 看 §1 四行的返回值判断 material/texture 覆盖是否被采纳 |
