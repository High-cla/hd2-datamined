# 25988413 上「内存访问」还剩什么（实测，2026-10-20 20:37–20:40）

> 一句话：**两条路都断了。** 进程内 —— `ffi` 没了；进程外 —— EAC 把 `PROCESS_VM_READ` 剥了。
> 但**地址空间地图还能拿**，而且足以定位 `game.dll` / `helldivers2.exe`。

目标进程：`helldivers2.exe` pid **6552**（非 WOW64，窗口 "HELLDIVERS 2"），EAC 内核驱动
`EasyAntiCheat_EOSSys` 处于 RUNNING。

## 1. 实测记录：同一个句柄，四种命运

用 `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`（`0x0410`）取得句柄，`OpenProcess` **成功**。
然后逐项试：

| 调用 | 需要什么权限 | 结果 | 备注 |
|---|---|---|---|
| `OpenProcess 0x1000 / 0x0410 / 0x1F0FFF` | — | **全部成功** | ★ **这个成功毫无意义**，见 §2 |
| `QueryFullProcessImageNameW` | QUERY_LIMITED | ✓ 成功 | 拿到镜像路径 |
| `GetProcessTimes` | QUERY_INFORMATION | ✓ 成功 | |
| `VirtualQueryEx` | QUERY_INFORMATION | ✓ **成功** | 走完 21,506 个区域 |
| `GetMappedFileNameW` | QUERY_INFORMATION | ✓ **成功** | 170 个映射文件 |
| `EnumProcessModules` / `…Ex` | 需要 VM_READ（读 PEB） | ✗ `err=5` | 与 §3 的模块表互为反证 |
| `ReadProcessMemory` | VM_READ | ✗ `err=5` | 地址取的是**已提交的 MEM_IMAGE 区**，不是野地址 |
| `MiniDumpWriteDump`（MiniDumpNormal） | VM_READ | ✗ `0x80070005 E_ACCESSDENIED`，文件 0 B | 整条转储管线断在这里 |

结论：EAC 的 `ObRegisterCallbacks` **不拒绝句柄，而是在创建时把 `PROCESS_VM_READ` 从请求的权限里剥掉**，
把剩下的（QUERY_INFORMATION 等）照常给你。

## 2. ★ 我踩进去的坑：一个不可能失败的判据

第一版 [tools/eac_access_test.py](../tools/eac_access_test.py) 只测了三档 `OpenProcess`，
三档全 GRANTED，于是它印出：

```
VERDICT: READABLE  external MiniDumpWriteDump should still work
```

**这是假阳性。** 三档都成功，是因为 EAC 让它们成功 —— 判据本身不能失败，所以它不是判据。
（本项目 DISCIPLINES §8.15 已经为同一类错误写过一次规则：*读自家产物的工具必须在最大产物上成功读过一次*。
这次是它的镜像：**测权限的工具必须真的读一个字节**。）

修正后的判据：先用 `VirtualQueryEx` 找到一个**已提交的 MEM_IMAGE 区域**，再 `ReadProcessMemory`
读 8 字节。这样 "handle 被剥权" 才表现为 FAIL，而不是表现为成功。

`--selftest` 加了同形变异：对自有子进程开一个**只要 `0x0400`（不含 VM_READ）** 的句柄 ——
`handle=True vq=True read=False err=5`，正好复刻 EAC 交回来的形状。5 PASS / 0 FAIL。

## 3. 还能做什么（这部分是真有用的）

`VirtualQueryEx` + `GetMappedFileNameW` 都只需要 `QUERY_INFORMATION`，所以**不读一个字节也能画出完整模块表**。

| 模块 | 映像基址 | 映像大小 | 区域数 |
|---|---|---|---|
| `game.dll` | `0x1ced0440000` | 51.51 MB | **1**（整块连续） |
| `helldivers2.exe` | `0x1ceb8520000` | 41.99 MB | **1**（整块连续） |
| `runtime.dll`（引擎） | `0x00ffab0000` | 123.88 MB | 28 |

进程总计：committed **11,150 MB**（与旧 build 那五份 10–11 GB 全量转储的体量吻合），
19,179 个 committed 区域，1,302 个 MEM_IMAGE 区域，**170 个映射文件**。

完整清单：[`../recon/addrspace-25988413.tsv`](../recon/addrspace-25988413.tsv)（170 行，含每文件的总字节数 / 基址 / 末址 / 区域数）。

**为什么这份表值钱**：两个主模块在内存里都是**单块连续**的，合计 93.5 MB。
一旦哪天拿到进程内读取能力，要抓的就是这两个区间 —— 不需要全量 11 GB，也不需要再扫。

## 4. 对既有工具的三态判定

| 工具 | 判定 | 依据 |
|---|---|---|
| `tools/crash_watch.py` → `dumper.ps1` → `MiniDumpWriteDump` | ✗ **死** | §1 的 `E_ACCESSDENIED` |
| `tools/memscan.py`（进程内 `ReadProcessMemory`） | ✗ **死** | `require("ffi")` → `module 'ffi' not found`（payload 第 11 行） |
| memscan 的"外部助手"修补方案 | ✗ **死** | 外部读 = §1 的 `err=5` |
| `tools/memmod_*` 写入路线 | ✗ **死** | 读都不行，写更不行 |
| 旧 build 的 6 份全量转储（`E:\hd2-dumps\kept\`） | ✓ **仍在** | 只对本 build 无效 |

## 5. 唯一剩下的路

Lua 侧**唯一的原生装载入口**还在：`package.loadlib` 是 function，`package.cpath` 含
`<game>\bin\?.dll`（`BootProbe.log:224/227`）。一个 46 KB 的 C 模块就能把 `rd()` / `VirtualQuery`
原样还回来 —— 甚至一个只调 `MiniDumpWriteDump(GetCurrentProcess(), …)` 的 5 行 DLL 就能恢复全量转储。

**代价**：那是往受 EAC 保护的进程里加载未签名模块。**未尝试，不建议在未明确决定前尝试。**

## 6. 没测的（别当成"不行"）

- **提权 —— 已测，没用（2026-10-20 21:0x）**：管理员窗口（标题栏 `管理员: …pwsh.exe`，工具自报
  `elevated=True`）对 pid 39648 重跑，逐行与普通权限完全相同 —— 三档 `OpenProcess` 仍全 GRANTED，
  `VirtualQueryEx` 仍 ok，`ReadProcessMemory` 仍 **`err=5`**，判定仍 FILTERED。
  即：**这不是 ACL 问题，提权解决不了**。剩唯一子格：`SeDebugPrivilege` **被显式启用**
  （管理员令牌里它默认 disabled），⚠ 推断仍无效 —— 剥权限的是 `ObRegisterCallbacks` 的 mask 改写，
  不是访问检查。
- `MiniDumpWithFullMemory`：没测，也没有必要测 —— `MiniDumpNormal` 都已经 `E_ACCESSDENIED`。
- `PROCESS_VM_WRITE` / `PROCESS_CREATE_THREAD`：没测，不为它去冒写内存的风险。

## 7. 复现

```
python D:\mod\tools\eac_access_test.py --selftest                    # 5 PASS / 0 FAIL
python D:\mod\tools\eac_access_test.py --pid <游戏pid> --dump-normal D:\mod\recon\eac-normal.dmp
```

第二行在 2026-10-20 20:39 的输出：

```
VERDICT: FILTERED  handle granted, PROCESS_VM_READ stripped -> external dump is DEAD
     MiniDumpNormal -> skipped (no VM_READ)
```

## 8. 「有没有 `PROCESS_VM_READ` 的替代品」—— 逐个实测，没有

问法是对的：如果只是 kernel32 那层的限制，换一个 API 就绕过去了。所以下面每一条都是**真的调用过**的，
不是从文档推的。第二个进程实例（pid **37880**，20:42 启动）上复现过同样的结果。

| 候选替代 | 它本来为什么可能绕过 | 实测结果 |
|---|---|---|
| `NtReadVirtualMemory`（ntdll 直调） | 绕过 kernel32 的包装层 | 同一句柄 → 同样被拒。对照组：对**自有进程的已映射地址**调用返回 `STATUS 0` 并读回 `ABCDEFGH`，证明调用本身写得对 |
| `QueryWorkingSetEx` | 只查页的驻留状态，不是读内容 | `err=5` |
| `PssCaptureSnapshot`（`PSS_CAPTURE_VA_CLONE`） | 内核自己克隆地址空间，看起来可以完全不看源句柄的 VM_READ | **`rc=5` ERROR_ACCESS_DENIED**（`0x0410` 与 `0x1F0FFF` 两种句柄都试了） |
| `PssCaptureSnapshot`（`PSS_CAPTURE_VA_SPACE`） | 只快照**布局**，也许连源句柄的 VM_READ 都不需要 | **`rc=0`，真的成功**（外部实测 2026-10-22；我们当时只试了 `VA_CLONE` 这一档）。但它给的是区域元数据 ≈ `VirtualQueryEx` 已有的东西；**读内容**要 `PssQuerySnapshot(PSS_QUERY_VA_CLONE_INFORMATION)` 的克隆句柄，那必须先 `VA_CLONE` → `rc=5`。⇒ 观测成立，**不是绕过** |
| 线程句柄 + `GetThreadContext` | 线程是另一种内核对象，也许只保护了 process | `OpenThread` 三档（`THREAD_GET_CONTEXT` / `THREAD_QUERY_INFORMATION` / `ALL`）**都成功**；`GetThreadContext` 一律 **`err=5`** |
| 从 EAC 服务进程复制句柄（`PROCESS_DUP_HANDLE`） | EAC 自己必然持有游戏的 VM_READ 句柄 | 那个进程连 `QUERY_LIMITED_INFORMATION` 都 **`err=5`** —— 它自身是受保护的 |
| `EnumProcessModules` | — | `err=5`（它内部要读 PEB） |

仍然可用的（**只有元数据，没有一个字节的内容**）：

| 还能用 | 实测 |
|---|---|
| `VirtualQueryEx` | ✓ 一次走完 18,170 个区域 |
| `GetMappedFileNameW` | ✓ 区域 → 文件名（170 个映射文件） |
| `GetProcessMemoryInfo` / `QueryFullProcessImageNameW` / Toolhelp 线程枚举（161 个线程） | ✓ |

**结论：没有替代品。** 上表每一条最后都收敛到同一个检查点 —— 句柄的 access mask，
在 `ObRegisterCallbacks` 里被改写。换 API 名字不改变这一点，换**进门方式**才可能。

真正能替代 `PROCESS_VM_READ` 的不是某个函数，而是位置：

1. **同进程** —— 读自己不需要这个权限。需要往进程里放代码（C 模块）——**已试并否证，见 §12**。
2. **让进程自己吐** —— 游戏自带的 `sie::CrashReportClient::CreateMinidumps(HANDLE, …)` 是进程内的，
   字符串里有 `full-minidump.dmp` / `--full-dump`，但它只在崩溃时跑。
3. **内核驱动 / 硬件 DMA** —— 超出范围。

## 9. 一条顺带的观察：模块基址每次启动都变

`game.dll` 的映像基址在 pid 6552 是 `0x1ced0440000`，在 pid 37880 是 `0x20902d10000`（ASLR）。
`runtime.dll` 两次都是 `0x00ffab0000`。所以 `recon/addrspace-25988413.tsv` 中的基址只对那一次进程实例有效，
**不能当常量用**；`VirtualQueryEx` + `GetMappedFileNameW` 每次现场重取即可（代价约 1 秒）。

## 10. 崩溃自动转储：一半还活着

`tools/crash_watch.py` 一直做两件事，在 EAC 之后这两件事的命运不同。

| 职责 | 判定 | 依据 |
|---|---|---|
| **抢救游戏自己的崩溃产物**（把 `crash_data/.temp` / `attachments` / `dumps` 拷到 E 盘） | ✓ **还能用** | 纯文件复制，不碰进程 |
| **自己抓全量内存**（`dumper.ps1` → `MiniDumpWriteDump`） | ✗ **废了** | §1：`E_ACCESSDENIED` |

本轮顺手修了 `crash_watch.py` 的两个问题：

1. **`crash_data/reports/<uuid>.dmp` 从来没被抢救过** —— 旧代码只走 `.temp` / `attachments` / `dumps`。
   而 crashpad **自己抓的那份转储**就落在 `reports/`，实测 4.2–6.5 MB，比 `dumps/` 那批 950 KB 的
   引擎小转储信息更多。这是本 build 上能拿到的最好的崩溃证据，之前每次崩溃都在漏掉它。
2. **没有前置检查**：旧版无条件调 `dumper.ps1`，在没有权限时会白等 900 秒再留一个 0 字节文件。
   现在先调 `can_read_memory()`（复用 `eac_access_test.probe_ops`），一句话说清为什么不行。

### 崩了到底能不能拿到全量转储？

| 路径 | 状态 |
|---|---|
| 外部 `MiniDumpWriteDump` | ✗ 实测死（§1） |
| 游戏自己的崩溃上报（**进程内**，不受句柄过滤影响） | ⚠ 未证实 |
| 抢一个"EAC 保护生效之前"的句柄 | ⚠ 未证实 |

关于第二条，`bin/crs-client.dll`（Crashpad + `sie::CrashReportClient`）里有一条 `--full-dump`
分支和一条 `--extended-dump` 分支，选择由客户端传给 handler 的一个 **options 位掩码**决定
（反汇编 RVB `0xb03d`：`test dil, 0x10` → `--full-dump`；`test dil, 0x08` → `--extended-dump`）。
但历史上落盘的全部是 4–6 MB 的 extended，**`full-minidump.dmp` 一次都没出现过**。所以这条是
"存在但从未被这条游戏用上"，不是"能用"。

关于第三条：句柄的 access mask 在创建那一刻就定死了，所以唯一可能拿到可读句柄的机会，是在
EAC 把这个进程标记为受保护之前。`tools/eac_early_handle.py` 就是去量这个窗口的（10 ms 轮询，
一见进程就开 `0x0410`，然后 t+0/1/5/15/30/60 秒各读 8 字节）。

---

## 11. ★ 实测：**杀掉 EAC 用户态服务，内存仍然读不了**（2026-10-21 00:18）

用户观察「在任务里把反作弊进程杀了也没导致退出」，要求核实它是否真的死了。
实测状态（游戏 pid **24840** 仍在运行，工作集 7.2 GB）：

| 组件 | 状态 |
|---|---|
| `EasyAntiCheat_EOS` 服务（`WIN32_OWN_PROCESS`） | **STOPPED** ← 被杀掉的就是它 |
| `EasyAntiCheat_EOSSys` **内核驱动**（`\??\C:\Program Files (x86)\EasyAntiCheat_EOS\EasyAntiCheat_EOS.sys`）| **RUNNING** |
| EAC 相关进程（tasklist） | **一个都没有** |

在这个状态下，对活着的游戏进程跑 `tools/eac_access_test.py --pid 24840`：

```
QUERY_INFORMATION|VM_READ (0x0410)   GRANTED
PROCESS_ALL_ACCESS    (0x1f0fff)     GRANTED
VirtualQueryEx                       ok
ReadProcessMemory                    DENIED err=5
VERDICT: FILTERED  handle granted, PROCESS_VM_READ stripped
```

**结论（✓ 实测）**：

1. **杀用户态服务 ≠ 关掉保护。** 保护是 `EasyAntiCheat_EOSSys` 内核驱动的 `ObRegisterCallbacks`
   在**建句柄时**改写 access mask；用户态那个服务只是扫描器/上报器。服务死了，剥权照旧。
2. **"进程还在跑"不是保护失效的证据** —— 游戏不退出只说明它不需要那个服务继续活着。
3. 于是 `PROCESS_VM_READ` 这条路**依旧封死**，且这次是在"反作弊服务已停"的理想条件下复测的，
   比之前更硬。

⚠ 剩下的唯一理论手段是卸载/停用那个内核驱动（`sc stop EasyAntiCheat_EOSSys`）。**不做**，理由：
① 驱动是保护对象，停用大概率直接失败或被立刻拉回；② 这是**反作弊篡改**，与"外观/非玩法 mod"
的既有策略相冲突，代价可能是封号；③ 即使停掉，也只是让"读内存"重新可用，而**写内存改玩法**
正是 EAC 明确要打的行为。若要试，需要用户明确指令，并且应当先记录风险。

---

## 12. ✗ 进程内原生代码：`package.loadlib` 被**镜像加载策略**挡住（2026-10-21 00:27）

### 12a. 为什么值得试

EAC 的 `ObRegisterCallbacks` 只管**别的进程**拿句柄。历史上的 memscan / memmod 是**进程内**
实现的（LuaJIT + `ffi` + RVA），**从来不需要 `PROCESS_VM_READ`**。所以"外部读被封"不等于
内存路线没了 —— 真正的墙是这个 VM **没有 `ffi`**。而进程内原生代码还有一条只记录过、
从没真试过的入口：

```
package.cpath = .\?.dll;<game>\bin\?.dll;<game>\bin\loadall.dll
cwd = <game>\（实测）        os.execute / io.popen = 真函数
```

### 12b. 判定方法（不需要编译器）

Lua 5.1 的 `package.loadlib` = `LoadLibraryA` + `GetProcAddress`，而且**失败时不抛错**，
返回 `(nil, <Win32 错误文本>)`。所以拿一份**真实存在的 DLL** 去问缺失符号，就能用错误码
区分"模块没映射"和"映射了但没符号"。

夹具 `tools/make_loadlib_fixtures.py`：把 `System32\version.dll`（DllMain 惰性）复制两份到游戏根目录
——`dshtest_signed.dll`（字节拷贝）、`dshtest_unsigned.dll`（把 `IMAGE_DIRECTORY_ENTRY_SECURITY` 归零）。

### 12c. 实测（routes 1.9.1，2026-10-21 00:27:01）

| 目标 | 返回码 | 含义 |
|---|---|---|
| `dsh_missing_module.dll` | **126** | 找不到指定模块 —— 说明 loadlib 真的走了 `LoadLibraryA` |
| `dshtest_unsigned.dll`（相对/绝对路径都一样）| **577** | **"Windows 无法验证此文件的数字签名"** |
| `dshtest_signed.dll` | **193** | "%1 不是有效的 Win32 应用程序" |

⚠ `193` 的字面意思是"PE 格式坏"，但**这里不是**：同一份字节在普通进程里能正常加载（见下面的对照
实验），所以 193 是**白名单拒绝码**，不是映像真的坏了。含义见 §12g 的两道闸门。

**对照实验（关键）**：同样这两个文件，在**普通 Python 进程里都能加载**
（`ctypes.WinDLL` 两个都拿到句柄）。⇒ 夹具是好的，**拒绝它的是游戏进程**。

### 12d. 结论

- **✗ 我们自己放进去的 DLL 无法被映射进游戏进程。**
  未签名 → 577（签名无法验证）；带签名但不在信任列表 → 193。
  **签名不是"无关"，而是"只能换错误码"**：自签、以及自签后再把证书装进 `LocalMachine\Root`
  让 `Get-AuthenticodeSignature` 报 `Valid`，结果**仍是 577**（§12g）。
  这是加载策略，不是文件损坏、不是路径问题、不是 `loadlib` 坏了（126 证明它工作）。
- 因此：**`ffi` 式的进程内内存读写无法恢复**。EAC 把"外部句柄"和"进程内原生代码"两条都堵了。
- 想绕过它就得篡改反作弊本身（停驱动 / 改加载策略）——那是明确的作弊规避，**不做**。

### 12e. 收尾状态

夹具与标记文件已从游戏根目录删除，`data\` 里**只剩 `patch_0`**（我们的 boot 加载器），
即 §6b 记录的干净隔离状态。游戏目录里不残留任何我们自己放的未签名 DLL。

### 12f. 于是"读"的最终账

| 路线 | 判定 |
|---|---|
| 外部读内存（`PROCESS_VM_READ` / dump / 任何 API 变体） | ✗ 句柄建时剥权（§11 再确认）|
| 进程内原生代码（`ffi` 等价物） | ✗ 本节的镜像加载策略 |
| **引擎 API（Lua 侧）** | ✓ 可用，但只有身份/位姿/资源，**没有玩法数值**（ENGINE-API §24）|
| **资源侧（`patch_N` 覆盖 + srkit）** | ✓ **唯一还能改东西的路** |

⇒ 结论：**"读游戏数值"这件事在本 build 上没有任何存活通道**；要做 mod 就只能走资源侧。

### 12g. 2026-10-22 外部复现：两道闸门 · `bin/plugins` 同命 · 一条未做的决胜实验

外部的独立小组在**同一个 build** 上把同一件事往下推了一步（
[issue #1](https://github.com/deepseekv41flash/hd2-25988413/issues/1)），其中**一条我们没做**：

**自签 + 受信根也不行。** `New-SelfSignedCertificate -Type CodeSigningCert` 签自己的 DLL →
证书导入 `Cert:\LocalMachine\Root`（管理员）→ `Get-AuthenticodeSignature` 从 `UnknownError`
变成 **`Valid`** → `loadlib` **仍然 `577`**。

⇒ 这**不是**"链到任意受信任根就行"，而是签名链校验钉在**它自己的根/发布者集合**上，与机器的
信任库无关。他也复现了我们的对照组（系统 DLL 改名 → **193**），和我们 §12c 一模一样。

四组数据放一起，只有一个模型能同时解释（⚠ 假设，未被单独证实）：

| 输入 | 返回 | 挂在哪 |
|---|---|---|
| 不存在的文件 | **126** | 没到闸门 |
| 未签名 / 自签（哪怕进了 `Root`） | **577** | **闸门 1**：签名链用**自钉根集**，不用系统信任库 |
| 微软签名的异名副本 | **193** | 闸门 1 过，**闸门 2**：文件不在白名单（名字/哈希） |
| 游戏自带、Arrowhead 签名、原地不动 | ✓ 映射 | 两闸都过 |

本机核对（2026-10-22）：`System32\version.dll` = `Valid / CN=Microsoft Windows`；
`bin\plugins\level_generation_pluginw64_release.dll`（625,752 B）与 `wwise_pluginw64_release.dll`
= `Valid / CN=Arrowhead Game Studios AB`。注意 **625,752** 这个字节数与外部报告一致。

**`bin/plugins` 同一条闸。** 外部把 `level_generation_pluginw64_release.dll` 换成只导出
`get_plugin_api` 的桩（`DllMain` 写日志），正常 Steam 启动、游戏正常进：**两版桩的日志都没生成**，
工作集 6.4 GB → 4.59 GB ⇒ 未签名文件在那个目录里**根本没有被 `LoadLibrary`**。

⚠ 那次判定用的是 `DllMain` 日志，属于**间接证据**（日志路径不可写/缓冲都会假阴性）。本仓库有更硬的
判定通道：`VirtualQueryEx` + `GetMappedFileNameW` 能直接列出**已映射**的文件（不需要加载成功，
§8 已实测 170 个映射文件）——再次验证时应当用这个。

⚠ 未验证、仅备查：外部转述"`bin/plugins` 的插件表要求 `debug_draw`(0x90) 与 `render`(0xa0) 非 NULL"
（引自 `BingusNativeBridge` v0.1.1 提交）。我们无签名加载能力，无法自证。

**决胜实验（2026-10-22，两轮实机跑完）：闸门 2 认「文件身份」，不认「文件内容」，也不是「目录授权」。**

探针 = boot 覆盖（`patch_0`）+ 一个 marker 文件门控，跑完逐字节还原。第一轮 16:30 六组，第二轮
16:35 补上第七组（同目录换名），七组全部拿到：

| 用例 | 夹具 | 返回 | 判定 |
|---|---|---|---|
| `control-missing` | 不存在的文件名 | **126** | 探针在工作 |
| `control-symbol` | `kernel32.dll` + 假符号 | **127** | `loadlib` 真的走到 `LoadLibraryA` |
| `unsigned-root` | 去掉证书表的 `version.dll` | **577** | 闸门 1 |
| `signed-root` | 微软签名副本，放根目录 | **193** | 闸门 2 |
| `signed-bin` | **同一份字节**，放 `<game>\bin\` | **193** | `bin\` 对它没有特权 |
| `signed-newname` | **Arrowhead 签名、在名单内的插件 DLL 逐字节复制**，换名放根目录 | **193** | ★ 内容一致也没用 |
| `signed-inplace` | 同一份字节，**放回 `bin\plugins\` 原目录**，只换名字 | **193** | ★★ **目录也没有特权 ⇒ 认的是文件名** |

原始日志（`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\BootProbe.log`，第二轮 16:35:41）：

```
--- loadlib gate matrix (opt-in marker dsh_loadlib_probe.on) ---
LOADLIB control-missing | dsh_missing_module.dll | 找不到指定的模块。
LOADLIB control-symbol | kernel32.dll | 找不到指定的程序。
LOADLIB unsigned-root | dshtest_unsigned.dll | system error 577
LOADLIB signed-root | dshtest_signed.dll | %1 不是有效的 Win32 应用程序。
LOADLIB signed-bin | bin\dshtest_bin.dll | %1 不是有效的 Win32 应用程序。
LOADLIB signed-newname | dshtest_copy.dll | %1 不是有效的 Win32 应用程序。
LOADLIB signed-inplace | bin\plugins\dshtest_p.dll | %1 不是有效的 Win32 应用程序。
```

`dshtest_copy.dll` / `dshtest_p.dll` 都是 `bin\plugins\level_generation_pluginw64_release.dll` 的
**逐字节副本**（625,752 B，md5 `3c2f18502b121138c5ce5b5ff95b879c`，签名 `Valid / Arrowhead`）。

⇒ 四条否证一起成立：

- "找个签名好的 DLL 塞进去" ✗ —— 内容/签名够好不是条件（`signed-newname`）；
- "放进 `package.cpath` 里的 `bin\`" ✗ —— 目录没有特权（`signed-bin`）；
- "放进 `bin\plugins\` 这个引擎自己的目录" ✗ —— **同目录换名仍然 193**（`signed-inplace`），
  所以闸门 2 的粒度是**文件名**，不是目录；
- 唯一能过的就是**游戏自己那份文件**（原名、原目录、原字节），而改它任何一个字节哈希就变
  ⇒ **到不了执行**。

> 附：`system error 577` 与 `%1 不是有效的 Win32 应用程序` 是 Lua 5.1 把
> `LoadLibrary` 的失败文本原样传回来的结果 —— 同一个 API 对不同的失败给不同的**文本形状**，
> 所以判读时不能只认中文串，还要认 `system error N`。
