# brain_box 内存积累问题分析

## 问题一：`NavigationService._active_trajectories` — 无限增长的轨迹字典

**位置**: `brain_box/navigation/service.py` 第 36 行
```python
self._active_trajectories: dict[str, NavigationTrajectory] = {}
```

**问题描述**:
- 每次调用 `/api/v1/navigation/instruction` 都会生成一条新 `NavigationTrajectory` 并存入该字典，key 为 UUID
- 字典**从不清理**：没有任何删除、过期、或上限逻辑
- 每条轨迹包含 `list[Waypoint]`，每个 Waypoint 含 lat/lon/alt/speed/hold_time/metadata 字段
- 服务运行时间越长、调用越多，该字典越大
- **这是最典型的内存泄漏点**：轨迹执行完毕后仍永久驻留内存

**是否需要迁移到 SQLite**: ✅ 是。轨迹是历史记录，执行完毕后即为冷数据。

---

## 问题二：`MAVLinkProtocol._devices` + `DroneManager._devices` — 离线设备永不清除

**位置**:
- `brain_box/communication/mavlink_comm.py` 第 275 行
- `brain_box/drone/manager.py` 第 27 行

**问题描述**:
- `MAVLinkProtocol._devices` 是所有通道共享的设备字典，`_process_heartbeat()` 只增不减
- `DroneManager._devices` 通过 `scan_now()` 接收协议层扫描结果，同样只增不减
- `_update_device_status()` 仅将超时设备标记为 `OFFLINE`，**不删除**
- 在真实 MAVLink 模式下，任何曾经连接过的 `system_id` 都会永久占据内存
- 无人机数量多、更换频繁时，大量离线设备记录积累

**是否需要迁移到 SQLite**: ⚠️ 部分。
- **在线设备**（`ONLINE`/`BUSY`）是热数据，必须留在内存以保证低延迟控制
- **长期离线设备**（超过一定时间未心跳）是冷数据，应持久化到 SQLite 并从内存移除
- 策略：超过 `heartbeat_timeout * N`（如 60 秒）未收到心跳的设备，写入 SQLite 历史表后从内存字典删除

---

## 问题三：`DroneManager._status_callbacks` — 回调列表只增不减

**位置**: `brain_box/drone/manager.py` 第 30 行
```python
self._status_callbacks: list[Any] = []
```

**问题描述**:
- `on_status_change()` 只追加，没有移除接口
- 目前只有 `EdgeReporter` 注册一次，实际影响极小
- 但如果未来多次调用（如重启 reporter 但不重建 manager），会导致重复回调积累

**是否需要迁移到 SQLite**: ❌ 否。这是设计缺陷，用 `set` 去重或提供 `remove_callback()` 即可，不涉及数据库。

---

## 迁移决策汇总

| 数据结构 | 位置 | 问题类型 | 处理方案 |
|---|---|---|---|
| `NavigationService._active_trajectories` | navigation/service.py | 无限增长，冷数据积累 | 迁移到 SQLite `trajectories` 表 |
| `MAVLinkProtocol._devices` / `DroneManager._devices` | mavlink_comm.py / drone/manager.py | 离线设备永不清除 | 超时设备写入 SQLite `device_history` 表后从内存删除 |
| `DroneManager._status_callbacks` | drone/manager.py | 设计缺陷（影响小） | 改为 `set` 或加移除接口，不需要 SQLite |

---

## SQLite 设计方案

### 数据库文件位置
`data/brain_box.db`（可通过配置覆盖）

### 表结构

#### `trajectories` 表（轨迹历史）
```sql
CREATE TABLE trajectories (
    trajectory_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    algorithm_name TEXT NOT NULL,
    total_distance REAL DEFAULT 0.0,
    estimated_time REAL DEFAULT 0.0,
    waypoints_json TEXT NOT NULL,   -- JSON 序列化的 waypoints 列表
    metadata_json TEXT DEFAULT '{}',
    created_at REAL NOT NULL,       -- Unix timestamp
    executed_at REAL,               -- 执行时间，NULL 表示未执行
    status TEXT DEFAULT 'pending'   -- pending / executed / failed
);
```

#### `device_history` 表（离线设备历史）
```sql
CREATE TABLE device_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    device_type TEXT NOT NULL,
    protocol TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    port INTEGER DEFAULT 0,
    last_heartbeat REAL NOT NULL,
    last_position_json TEXT DEFAULT '{}',
    metadata_json TEXT DEFAULT '{}',
    evicted_at REAL NOT NULL        -- 从内存移除的时间
);
```

### 内存中仍保留的数据（热数据）
- `DroneManager._devices`：仅保留 `ONLINE` / `BUSY` / `ERROR` 状态的设备（最近 60 秒内有心跳）
- `NavigationService._active_trajectories`：仅保留 `pending`（未执行）的轨迹，执行后立即写入 SQLite 并从内存移除
