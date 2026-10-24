# 同一资源 id 出现在两个补丁里，引擎认哪个？（build `26088801`）

> 2026-10-24 · 状态：**✓✓ 实机**（一局定案：**高号胜**）
> 这条问题在我们的 `PATCH-LOADER-DESIGN-26088801.md` §4 里挂了 **3 天**（标 OPEN），
> 它决定 `tools/patch_compose.py merge` 的合并语义，也决定社区 loader（BSL v21）那句"号大者胜"到底对不对。

## 1. 问题

`data/9ba626afa44a3aa3.patch_N` 是按序号叠加的补丁包。如果**两个不同序号的补丁里放了同一个资源 id**：

| 候选规则 | 含义 |
|---|---|
| **低号胜** | 引擎按 0→255 顺序叠加，**先到先得**（后续同名被忽略） |
| **高号胜** | 后到覆盖，**号大者胜**（BSL v19/v21 的 `higher_patch` 假设） |
| 都不胜 | 冲突导致该 id 解析失败，或两个都加载 |

我们从来没测过。BSL v21 的发现器（`src/discover.lua` 同款）**假设高号胜**并用它做"副本遮挡"提示
（`not started: <name>, declared in <A>, is hidden by <B>`），但那是**推断，不是实测**。

## 2. 实验设计（零内容风险）

利用一个已经存在的事实：我们装的 `patch_0`（BootProbe 1.3.0）在启动时会扫 `mods/auto/1..6`，
对每个名字 `Application.can_get("lua", name)` → 存在就 `require(name)`。

于是：

| 补丁 | 内容 | 资源 id |
|---|---|---|
| `patch_5` | lua 模块 `mods/auto/5`，只做一件事：往 `SameIdProbe.log` 追加一行 `COPY=A declared_in=patch_5` | `0xF2EFDB8354D99D1D` |
| `patch_6` | **同一个 id**，正文只改标记：追加 `COPY=B declared_in=patch_6` | `0xF2EFDB8354D99D1D` |

- 两个补丁都**只含一条 lua 记录**，不碰任何已有补丁；序号 0..6 保持连续（我们的 `LOADER-SPEC` 要求连续）。
- 引擎只会解析出**一个** `mods/auto/5`，被 `require` 执行的那份**自己写日志** ⇒ 日志里出现哪一行就是谁赢了。
- 生成器/回滚：`D:\mod\sameid-probe\sameid_build.py`（`--remove` 一键删干净）。

### 2.1 离线预检（已做）

| 检查 | 结果 |
|---|---|
| `srkit list` 两个补丁的 id 相同 | ✓ 都是 `0xF2EFDB8354D99D1D`，各 1 条 `lua` 记录，904 B toc |
| `srkit check` 解码/重编码逐字节一致 | ✓ 2/2，0 失败 |
| Lua 5.1 语法（`lupa.lua51`，真 Lua 5.1） | ✓ 两份都 OK |
| Lua 5.1 运行（`loadstring` + 调 `mods/auto/5`） | ✓ 都返回 `{copy="A"/"B", patch=5/6, name="mods/auto/5"}`，日志行格式符合预期（离线产物 `offline-SameIdProbe.log`） |

## 3. 预测（开跑前写死）

| 观察 | 判读 |
|---|---|
| `SameIdProbe.log` 只有 `COPY=B declared_in=patch_6` | **高号胜** —— BSL v21 的假设成立 ⇒ `patch_compose` 可以安全地"用高号覆盖低号" |
| 只有 `COPY=A declared_in=patch_5` | **低号胜** —— v21 的遮挡提示会把方向说反；我们的合并器必须"低号优先/只往新号追加" |
| 两行都有 | 引擎把两份都加载了（同一 id 不互斥）⇒ 需要看 `require` 到底返回哪个 |
| 一行都没有 + BootProbe 记 `require FAILED` | 同 id 冲突导致解析失败 ⇒ 这也是结论：**绝不能撞 id** |
| BootProbe 记 `mods/auto/5 -> absent` | 两个补丁都没被看见 ⇒ 补丁没加载（先查文件/序号连续性） |

不管哪种结果，`BootProbe.log` 的 `mods/auto/5 -> present, required OK (type table)` 那一行都是"跨补丁合并
确实把这个 id 合并进来了"的旁证。

## 4. 读日志

```bash
# 赢家
cat "$LOCALAPPDATA/CowboyBingus/Helldivers2/Logs/SameIdProbe.log"
# 扫描结果（找 mods/auto/5 那行，以及 SWEEP RESULT）
grep -n "mods/auto/5\|SWEEP RESULT\|Application.can_get" \
    "$LOCALAPPDATA/CowboyBingus/Helldivers2/Logs/BootProbe.log" | tail -8
```

## 5. 回滚

```bash
cd /d/mod/sameid-probe && python sameid_build.py --remove
```

只删 `patch_5` / `patch_6` 及其两个 0 B 伴生文件，共 6 个；不触碰 0..4。

## 6. ✓✓ 结果（2026-10-24 11:46 局）

| 项 | 值 |
|---|---|
| 局次 | `BootProbe 1.3.0 | 2026-10-24 11:46:29`（`BootProbe.log:124241`） |
| `SameIdProbe.log` | **只有 1 行**：`COPY=B declared_in=patch_6 required_as=mods/auto/5` |
| BootProbe 扫描（本局） | `mods/auto/5 -> present, required OK (type table)`；`SWEEP RESULT: 4 found, 4 loaded, 2 absent`（`BootProbe.log:124904-124913`） |
| 对照组（上一局，补丁未装） | 同一个探针同一位置：`mods/auto/5 -> absent (ok=true value=false)`；`SWEEP RESULT: 3 found, 3 loaded, 3 absent`（`BootProbe.log:124201-124210`） |
| **判定** | **高号胜** —— `patch_6` 的副本被解析，`patch_5` 的副本被丢弃 |

### 6.1 为什么这个结论是干净的

| 疑点 | 排除依据 |
|---|---|
| 是不是"内容不同所以选了 B"？ | 两份正文**只差标记字符串**（`COPY=A patch=5` vs `COPY=B patch=6`），引擎不解析正文 |
| 是不是两份都加载了？ | `SameIdProbe.log` **只有 1 行**；两份都跑会留 2 行 |
| 是不是补丁根本没被看见？ | 上一局同一名字是 `absent`，本局变成 `present, required OK` —— **同探针/同位置的前后对照** |
| 是不是 `require` 缓存骗人？ | 只有一份的正文被执行过（日志 1 行），缓存只能返回执行过的那份 |

### 6.2 顺带钉死的两件事

1. **BSL v19/v21 的"号大者胜"假设成立** —— 它的 `higher_patch` + `hidden by` 方向是对的，可以放心引用。
2. **同名 id 不互斥、也不报错**：引擎安静地取高号那份，低号那份不生效、无警告。
   ⇒ 安装目录里出现同 id 多补丁时，**光看文件列表判断"谁在生效"是错的**，必须按序号取最大。

### 6.3 对合成器与部署器的直接后果

| 事项 | 结论 |
|---|---|
| `tools/patch_compose.py merge` 的"同 id 冲突默认拒绝" | **仍然正确**（一个补丁包内不该出现两条同 id 条目），但现在我们知道**跨补丁**撞 id 的语义了 |
| 更新一个已装的 mod | 可以**装到更高序号**实现覆盖（引擎保证生效），不必改原文件 —— BSL 的做法是对的 |
| 想遮掉某个社区 mod 的资源 | 在**更高序号**放同 id 的替代条目即可，不动对方文件 |
| 判断"当前实际生效的是哪份" | 必须取**最大序号**的那份，不能靠文件名猜 |

### 6.4 ⚠ 一条要记住的坑（我们自己的探针）

`BootProbe.log` 的会话头写的是 `build 25988413`，但**那是 BootProbe 自己的版本字符串，不是引擎 build**
（现在跑的是 `26088801`）。引用日志时别把它当 build 证据。
