# 同一资源 id 出现在两个补丁里，引擎认哪个？（build `26088801`）

> 2026-10-24 · 状态：**实验已布好，等一局实机**（预测先行，见 §3）
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

## 6. 结果（待填）

| 项 | 值 |
|---|---|
| 局次 | — |
| `SameIdProbe.log` | — |
| 判定 | — |
