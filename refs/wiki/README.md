# 外部数据快照

## stratagemdata.json

* 来源：<https://helldivers.wiki.gg/wiki/Module:Decodedata-Attacks/stratagemdata.json>
  （社区解码的**战备道具资源**，含 `ref` / `projectile_type` / `attacks` / `stratcode`）
* 抓取：2026-10-22，55,541 B，原样保存，未改动。
* 用途：只取**语义字段**（`ref` 对应 `StratagemType` 名，`projectile_type` 对应弹丸类型名，
  `attacks` 是解析出的攻击树）。**不取数值**——这份数据来自另一个 build
  （它写 Orbital Precision Strike 冷却 90，本 build 与 wiki 页面都是 80）。
* 与本地数据的对照见 `docs/STRATAGEM-REFERENCE-CHAIN-25988413.md` §4.1。

## modules.json

`Module:` 命名空间 276 个页面的 API 清单（`action=query&list=allpages`），用来找到那份数据模块。

## 不随仓库分发的内容

其余数据模块（`Decodedata-Attacks/*.json` 等，合计约 1.3 MB）**不放进本仓库**——那是 wiki 的
内容，随需自己拉：

```bash
python tools/fetch_wiki_modules.py --out refs/wiki/modules
```

用途：**字段名与结构参照**，见 `docs/WIKI-DATA-MODULES.md`。
不用途：数值基准——多个模块来自不同 build（`stratagemdata.json` 写 Precision Strike 冷却 90，
本 build 是 80；`S_P15_IE` 的 `cone_angle` 写 35，本 build 是 27）。
