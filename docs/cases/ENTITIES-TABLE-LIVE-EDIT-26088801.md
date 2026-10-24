# 实体表（`generated_entities.dl_bin`）在线改写 —— 实机已证（build 26088801）

> **一句话：47 MB 的核心实体表可以改、可以重新封装、引擎照收、实机生效。**
> 这是「数据表路线」第一次打通**实体组件表**（此前只打通设置表与 customization 表）。
> 首例判据：把 P-92 Warrant 的锁定距离 60 m → 300 m，进图后**能锁 60 m 以外的目标** ✓。

---

## 1 为什么这一条值得单独记

| 以前 | 现在 |
|---|---|
| `.dl_bin` 可改路线只覆盖 `generated_*_settings` / `generated_customization_*`（小表、几 KB–几百 KB） | 覆盖到 **`generated_entities.dl_bin`**（47,259,396 B、275 个 `LDLD` 块、全部实体组件） |
| 改实体数据只能走 **memmod**（进程内存、重启即失效、要重装/重进图） | **持久**：文件替换，重启仍在 |
| 语义/数值/组件类改动没有「离线可证 + 上机可验」的通道 | 有：`entity_field_set.py`（门禁 G1–G9）→ `seal-key` → `dlbin_deploy.py` |

⇒ 能力边界从「能改设置与小表」扩到「**能改任意实体组件的任意字段**」。

---

## 2 实机结果

| 项 | 内容 |
|---|---|
| 变量 | P-92 Warrant `SensorEyeComponentData +0x00 distance`：**60.0 → 300.0** |
| 用户实机判定 | **「能锁上超过 60 m 的」** ✓ |
| 推论 | ① `distance` 就是锁定距离字段；② 引擎接受我们重新封装的实体表；③ 组件表在**启动时**读，重启即生效 |

判据为什么干净：这是**单变量**（整份明文与基线只差 3 字节），且 P-92 原版 60 m 是**已知值**
（社区实测与表值 5/5 吻合，见 [LOCKON-TARGETING](../tables/LOCKON-TARGETING-26088801.md) §2）。

---

## 3 证据链（每一步都可复跑）

| # | 步 | 结果 |
|---|---|---|
| 1 | 盘上密文用 `open-key --key recipient.sk` 解封 | 与基线明文**逐字节相同**（sha256 `dc6d52a1…`，47,259,396 B） |
| 2 | 明文内容哈希 `MurmurHash64A(seed 0xDEADBEEFABAD1DEA)` | `0x8E49771B181FFAA1` = `entity_field_set.py` 的 `ANCHOR` |
| 3 | `entity_field_set.py set` 改字段 | G1–G9 全 PASS，哈希仍 `0x8E49771B181FFAA1` |
| 4 | `seal-key --key recipient.pk` | 47,259,456 B（= 明文 + 48） |
| 5 | `open-key` 解回 | 与我们改后的明文**逐字节相同** |
| 6 | `dlbin_deploy.py install` | 装盘，备份 `cac4a228…` 留在 `D:\mod\backups\dlbin-deploy\game\` |
| 7 | **盘上回读**（不信工具自述） | live sha256 == 我们的密文；解封后字段读回 **300.0** |
| 8 | 实机 | ✓ 能锁 60 m 以外 |

---

## 4 可复现命令

```bash
cd D:/mod/work/repo-datamined

# 1) 改字段（f32）
python tools/entity_field_set.py set --block 0x14729B6A --key 0xCF8934FF6567A42D \
    --field 0x0 --type f32 --value 300 --expect-old 60 --out out/X.plain

# 2) 封装
python tools/dlbin_seal.py seal-key out/X.plain --key refs/dlbin/keys/recipient.pk \
    --out out/generated_entities.dl_bin

# 3) 盘上回读验证（务必做，别只看解封往返）
python tools/dlbin_seal.py open-key "<游戏>/data/game/generated_entities.dl_bin" \
    --key refs/dlbin/keys/recipient.sk --out out/readback.plain

# 4) 装机 / 回滚
python tools/dlbin_deploy.py install --file generated_entities.dl_bin --sealed out/generated_entities.dl_bin
python tools/dlbin_deploy.py restore --file generated_entities.dl_bin
```

**链式改动**：把上一次的输出当 `--plain` 再跑一次即可（哈希已保住）。
第 2 轮（锥角）就是这么叠在第 1 轮（距离）上面的。

---

## 5 已知边界 / 坑

| 项 | 状态 |
|---|---|
| 必须**保住内容哈希** `0x8E49771B181FFAA1` | ✓ 工具强制（G3）；做法 = 末块 payload 尺寸 += pad+8、尾部追加零区、校正字解在尾部 |
| `seal-key` 每次新随机 ephemeral ⇒ 同一份明文封两次**字节不同** | 正常；比内容只比**明文**哈希，不比封包哈希 |
| 封包必须用**游戏内置那对密钥** | 自己生成一对能让命令跑通，但引擎解不开 |
| 组件表在**游戏启动时**读 | 改完必须**重启**；进任务拿武器后才看到效果 |
| 装机前确认游戏**没在跑** | 否则文件被占用 / 读旧数据 |
| `TargetingComponentData` 不是玩家锁定（是 AI 索敌） | 别按名字误伤，见 [LOCKON-TARGETING](../tables/LOCKON-TARGETING-26088801.md) §6 |
| 容器方言与设置表不同 | 实体表是 **28 B 块头 / 无组数前缀**，`plain_edit.py` 的 24 B 假设**不适用**；用 `entity_field_set.py` |

---

## 6 三态

| 主张 | 态 |
|---|---|
| 盘上实体表 = 我们基线的密封版（同钥可解、逐字节一致） | **✓ 离线 + 实机文件一致** |
| 改字段后能重新封装，且解回逐字节一致 | **✓ 离线** |
| 引擎**接受**改过的实体表并生效 | **✓ 实机**（锁定距离 60→300） |
| 组件/数值表在启动时读、出生时应用 | **✓ 实机**（沿用既有结论） |
| 同一路数可推广到**任意**组件任意字段 | **⚠ 未逐个验证**（结构上通用，需按字段做单变量） |
| 加行 / 改行数（不只改值）在实体表上是否同样可行 | **⚠ 未试** |
