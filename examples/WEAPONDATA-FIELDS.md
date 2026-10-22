# WeaponDataComponentData 字段图（build 25988413）

> 这份文档回答「`entities` 里 `WeaponData` 每行记录的字段在第几字节」。
> 结论来自三处交叉：DLC `dl_library.dl_typelib` 的成员偏移、`xypwn/filediver` 的 Go 结构体字段名与顺序、以及**真实数据取值核对**。

## 1. 块布局

`generated_entities.dl_bin` 是「块序列」。`WeaponDataComponentData` 块的 payload 分两段：

```
payload = [ hashmap 11,936 B ][ row array 463,760 B ]
row       = 1,240 B × 374 行
hashmap   = 16 B 一条槽位 { u64 资源哈希, u32 行号, u32 填充 }
```

- **键** = 武器资源哈希（Murmur64A），与 `LoadoutEntryComponentData` / `EquipmentComponentData` **同一命名空间**，可以用同一个键反查
- **值** = 行号（0..373）
- 行地址 = `块 payload 起点 + 11,936 + 行号 × 1,240`

```
块起点            0x0193CCE8（type 0x88E4DBB1）
payload 起点      0x0193CD04
hashmap           payload + 0        .. +11,936
row array         payload + 11,936   .. +475,696
```

## 2. 字段表（行内偏移）

| 偏移 | 大小 | 字段 | 类型 |
|---|---|---|---|
| +0 | 60 | `RecInfo` 后坐力 | `RecoilInfo` |
| +60 | 24 | `RecModifiers` 后坐力修正 | `RecoilModifiers` |
| +84 | 12 | `Spread` 散布 | `SpreadInfo` |
| +96 | 8 | `SpreadMods` 散布修正 | `SpreadModifiers` |
| +104 | 4 | `SwayMultiplier` 摆动倍率 | float32 |
| +108 | 4 | `AimBlockLength` 瞄准阻挡长度 | float32 |
| +112 | 1 | `IsSuppressed` | bool |
| +116 | 12 | `AimZoom` 瞄准倍率 | Vec3 |
| +128 | 4 | `ScopeSway` 镜内摆动 | float32 |
| +132 | 1 | `NoiseTemplate` | enum |
| +136 | 4 | `VisibilityModifier` 开火可见度 | float32 |
| +140 | 4 | `NumBurstRounds` 点射发数 | uint32 |
| +144 | 4 | `PrimaryFireMode` | enum (1=auto 2=single 3=burst) |
| +148 | 4 | `SecondaryFireMode` | enum |
| +152 | 4 | `TertiaryFireMode` | enum |
| +156 | 4 | `QuaternaryFireMode` | enum |
| +160 | 24 | `UnknownMinigunStruct` | 24 B |
| +184 | 8 | `FunctionInfo` | `WeaponFunctionInfo` |
| +192 | 8 | `Crosshair` 准星材质 | Hash |
| +200 | 1 | `AlwaysShowCrosshair` | bool |
| +204 | 96 | `FireNodes` 出弹节点 ×24 | ThinHash[24] |
| +300 | 4 | `AimSourceNode` | ThinHash |
| +304 | 1 | `SimultaneousFire` | bool |
| +308 | 8 | `ScopeCrosshair` 准星屏幕位置 | Vec2 |
| +316 | 12 | `UnknownVec3` | Vec3 |
| +328 | 8 | `Unknown2dVec` | Vec2 |
| +336 | 1 | `UnknownMinigunBool` | bool |
| +340 | 12 | `ScopeZeroing` 归零档位 | Vec3 |
| +352 | 1 | `ScopeLensHidesWeapon` | bool |
| **+356** | 4 | **`Ergonomics` 人机响应** | **float32** |
| +360 | 4 | `UnknownFloat` | float32 |
| +364 | 1 | `UnknownMinigunBool2` | bool |
| +368 | 8 | `Unknown2dVec2` | Vec2 |
| +376 | 8 | `Unknown2dVec3` | Vec2 |
| +384 | 1 | `ConstrainedAimLeading` | bool |
| +385 | 1 | `AllowFPV` | bool |
| +386 | 1 | `AllowAiming` | bool |
| **+387** | 1 | **`FirePreventsMovement` 站姿惩罚** | **bool** |
| +388 | 4 | `StartFiringMinigunAnimationEvent` | ThinHash |
| +392 | 4 | `StopFiringMinigunAnimationEvent` | ThinHash |
| +396 | 4* | `UnknownBool2` | bool(padded) |
| +400 | 1* | `CrosshairType` | enum |
| +404 | 4* | `FirstPersonSightNodes` | `OpticSetting`（实际占更大区段）|
| +408 | 48* | ⚠ 之后与 typelib 有错位 | — |

> \* 标星的行：`filediver` 的 Go 定义可能落后于本 build（例如 1 字节 bool 在 typelib 里占 4 字节），**+396 之后偏移可能有 ±4 漂移**，改之前请用真实取值核对

## 3. 嵌套结构字段

**`RecoilInfo`（60 B，+0）**

| 偏移 | 字段 |
|---|---|
| +0 | `Drift` 枪口漂移（28 B） |
| +28 | `Climb` 镜头上爬（28 B） |
| +56 | `UnkFloat` |

**`RecoilComponentInfo`（28 B）**

| 偏移 | 字段 | 含义 |
|---|---|---|
| +0 | `HorizontalRecoil` | 水平后坐（度/秒），两段值 |
| +4 | `VerticalRecoil` | 垂直后坐（度/秒） |
| +8 | `UnkFloat1` | |
| +12 | `UnkFloat2` | |
| +16 | `HorizontalBias` | 水平偏向（起/终） |
| +20 | `RandomAmount` Vec2 | 随机占比（0–1） |

**`RecoilModifiers`（24 B，+60）**：`HorizontalMultiplier` / `VerticalMultiplier` / `DriftHorizontalMultiplier` / `DriftVerticalMultiplier` / `ClimbHorizontalMultiplier` / `ClimbVerticalMultiplier`

**`SpreadInfo`（12 B，+84）**：`Horizontal`（mrad）@+0、`Vertical`（mrad）@+4、`UnknownBool`@+8
**`SpreadModifiers`（8 B，+96）**：`Horizontal`@+0、`Vertical`@+4
**`WeaponFunctionInfo`（8 B，+184）**：`Left`@+0、`Right`@+4

## 4. 实测核对：AR-23 Liberator

取 `LoadoutEntryComponentData` 里显示名为 `AR-23 Liberator` 的键 `0x968211C0033DCE64`，在 `WeaponData` 的 hashmap 查到行号 **273**，解出的值：

```
row 273 @0x19925FC
  Ergonomics(+356)           = 65.000
  FirePreventsMovement(+387) = 0
  SwayMultiplier(+104)       = 1.000
  ScopeSway(+128)            = 1.000
  NumBurstRounds(+140)       = 3
  FireModes(+144..+156)      = (1, 2, 3, 0)     ← auto / single / burst
  RecoilInfo(+0, 60B)        = (7.0, 10.0, 90.0, 90.0, 0.0, 0.1)
  Spread(+84, 12B)           = (2.0, 2.0, 0)
  SpreadMods(+96, 8B)        = (1.0, 1.0)
```

数值全部落在合理区间（人机 65、单发/三连发配置、后坐 7–10 度/秒），说明字段图成立。

## 5. 怎么自己定位一把武器

1. 拿武器的**资源哈希**（`LoadoutEntryComponentData` 的键，或 `murmur64(资源路径)`）
2. 在 `WeaponData` 块 payload 的前 11,936 B 里按 16 字节步进找 `{u64 哈希 → u32 行号}`
3. 行地址 = `payload + 11,936 + 行号 × 1,240`

`parse_examples.py` 已经能打印 hashmap：

```bash
python parse_examples.py --slots generated_entities.dl_bin 0x193CCE8 --limit 5
```

## 6. 其他组件的行结构（同样方法可解）

| 组件 | 块偏移 | hashmap | 行结构 |
|---|---|---|---|
| `ProjectileWeaponComponentData` | 0x02CDE0B8 | 8,896 B | 616 B × 279 |
| `EquipmentComponentData` | 0x0191B790 | 11,232 B | 232 B × 352 |
| `LoadoutEntryComponentData` | 0x000B07D8 | 6,368 B | 32 B × 199 |
| `LoadoutPackageComponentData` | 0x000A7E18 | 16 B 头 + 槽位 | 待解 |

生成任意组件的字段表：

```bash
python entity_fields.py --component WeaponDataComponentData
```
