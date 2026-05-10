# BrainBox 类脑盒子 — API 完整参考

> 所有接口均使用 **POST** 方法，请求/响应体均为 **JSON**。

---

## 目录

- [一、输入接口（外部 → 类脑盒子）](#一输入接口外部--类脑盒子)
  - [1.1 无人机扫描](#11-无人机扫描)
  - [1.2 无人机查询](#12-无人机查询)
  - [1.3 无人机汇总](#13-无人机汇总)
  - [1.4 无人机控制指令](#14-无人机控制指令)
  - [1.5 导航指令下发](#15-导航指令下发)
  - [1.6 轨迹执行](#16-轨迹执行)
  - [1.7 活动轨迹列表](#17-活动轨迹列表)
  - [1.8 可用导航算法列表](#18-可用导航算法列表)
  - [1.9 系统状态](#19-系统状态)
  - [1.10 已注册通信协议](#110-已注册通信协议)
- [二、输出接口（类脑盒子 → 边缘控制服务）](#二输出接口类脑盒子--边缘控制服务)
  - [2.1 心跳上报](#21-心跳上报)
  - [2.2 无人机状态上报](#22-无人机状态上报)
  - [2.3 无人机状态变化即时上报](#23-无人机状态变化即时上报)
  - [2.4 导航轨迹上报](#24-导航轨迹上报)
- [三、统一响应格式](#三统一响应格式)
- [四、数据结构定义](#四数据结构定义)

---

## 一、输入接口（外部 → 类脑盒子）

这些接口由类脑盒子 HTTP 服务器提供，供边缘控制服务或其他系统调用。

---

### 1.1 无人机扫描

立即扫描当前网络下的所有无人机。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/drones/scan` |
| **调用方** | 边缘控制服务 / 运维系统 |
| **请求体** | 无（空 body 或 `{}`） |

**请求样例：**
```http
POST http://192.168.1.50:9000/api/v1/drones/scan
Content-Type: application/json

{}
```

**响应样例：**
```json
{
  "success": true,
  "message": "扫描完成，发现 3 台设备",
  "data": [
    {
      "device_id": "drone_sim_0",
      "device_type": "quadcopter",
      "protocol": "mavlink",
      "status": "online",
      "ip_address": "127.0.0.1",
      "port": 14550,
      "last_heartbeat": 1715340000.123,
      "position": {
        "latitude": 39.9042,
        "longitude": 116.4074,
        "altitude": 100.0
      },
      "metadata": {
        "autopilot": "simulated",
        "mav_type": "quadrotor",
        "system_status": "active"
      }
    },
    {
      "device_id": "drone_sim_1",
      "device_type": "quadcopter",
      "protocol": "mavlink",
      "status": "online",
      "ip_address": "127.0.0.1",
      "port": 14551,
      "last_heartbeat": 1715340000.456,
      "position": {
        "latitude": 39.9052,
        "longitude": 116.4084,
        "altitude": 110.0
      },
      "metadata": {
        "autopilot": "simulated",
        "mav_type": "quadrotor",
        "system_status": "active"
      }
    }
  ]
}
```

---

### 1.2 无人机查询

按条件查询已发现的无人机信息。所有过滤条件均为可选。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/drones/query` |
| **调用方** | 边缘控制服务 / 其他系统 |

**请求体格式：**
```json
{
  "device_id": "string | null",      // 指定设备 ID（精确查询）
  "device_type": "string | null",    // 按设备类型过滤 (quadcopter, hexarotor, ...)
  "protocol": "string | null",       // 按协议过滤 (mavlink, ...)
  "status": "string | null"          // 按状态过滤 (online, offline, busy, error)
}
```

**请求样例 — 查询指定设备：**
```http
POST http://192.168.1.50:9000/api/v1/drones/query
Content-Type: application/json

{
  "device_id": "drone_sim_0"
}
```

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": {
    "device_id": "drone_sim_0",
    "device_type": "quadcopter",
    "protocol": "mavlink",
    "status": "online",
    "ip_address": "127.0.0.1",
    "port": 14550,
    "last_heartbeat": 1715340000.123,
    "position": {
      "latitude": 39.9042,
      "longitude": 116.4074,
      "altitude": 100.0
    },
    "metadata": {
      "autopilot": "simulated",
      "mav_type": "quadrotor",
      "system_status": "active"
    }
  }
}
```

**请求样例 — 按状态查询所有在线设备：**
```http
POST http://192.168.1.50:9000/api/v1/drones/query
Content-Type: application/json

{
  "status": "online"
}
```

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": [
    {
      "device_id": "drone_sim_0",
      "device_type": "quadcopter",
      "protocol": "mavlink",
      "status": "online",
      "ip_address": "127.0.0.1",
      "port": 14550,
      "last_heartbeat": 1715340000.123,
      "position": { "latitude": 39.9042, "longitude": 116.4074, "altitude": 100.0 },
      "metadata": { "autopilot": "simulated", "mav_type": "quadrotor", "system_status": "active" }
    }
  ]
}
```

**设备不存在时的响应：**
```json
{
  "success": false,
  "message": "设备 drone_999 未找到",
  "data": null
}
```

---

### 1.3 无人机汇总

获取所有无人机的汇总统计信息。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/drones/summary` |
| **调用方** | 边缘控制服务 / 监控面板 |
| **请求体** | 无（空 body 或 `{}`） |

**请求样例：**
```http
POST http://192.168.1.50:9000/api/v1/drones/summary
Content-Type: application/json

{}
```

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": {
    "total": 3,
    "online": 3,
    "offline": 0,
    "devices": [
      {
        "device_id": "drone_sim_0",
        "device_type": "quadcopter",
        "protocol": "mavlink",
        "status": "online",
        "ip_address": "127.0.0.1",
        "port": 14550,
        "last_heartbeat": 1715340000.123,
        "position": { "latitude": 39.9042, "longitude": 116.4074, "altitude": 100.0 },
        "metadata": { "autopilot": "simulated", "mav_type": "quadrotor", "system_status": "active" }
      }
    ]
  }
}
```

---

### 1.4 无人机控制指令

向指定无人机发送控制指令。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/drones/command` |
| **调用方** | 边缘控制服务 |

**请求体格式：**
```json
{
  "device_id": "string",         // 必填，目标设备 ID
  "command": {                   // 必填，指令内容
    "type": "string",            // 指令类型: arm, disarm, takeoff, land, goto
    "altitude": "float",         // takeoff 时使用
    "latitude": "float",         // goto 时使用
    "longitude": "float",        // goto 时使用
  }
}
```

**请求样例 — 解锁（arm）：**
```http
POST http://192.168.1.50:9000/api/v1/drones/command
Content-Type: application/json

{
  "device_id": "drone_sim_0",
  "command": {
    "type": "arm"
  }
}
```

**响应样例：**
```json
{
  "success": true,
  "message": "指令已发送",
  "data": {
    "success": true,
    "message": "模拟发送指令 arm 到 drone_sim_0"
  }
}
```

**请求样例 — 起飞（takeoff）：**
```json
{
  "device_id": "drone_sim_0",
  "command": {
    "type": "takeoff",
    "altitude": 50.0
  }
}
```

**请求样例 — 前往指定位置（goto）：**
```json
{
  "device_id": "drone_sim_0",
  "command": {
    "type": "goto",
    "latitude": 39.91,
    "longitude": 116.41,
    "altitude": 100.0
  }
}
```

**请求样例 — 降落（land）：**
```json
{
  "device_id": "drone_sim_0",
  "command": {
    "type": "land"
  }
}
```

---

### 1.5 导航指令下发

边缘控制服务下发导航指令，类脑盒子调用导航算法生成轨迹，并自动将轨迹上报给边缘服务。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/navigation/instruction` |
| **调用方** | 边缘控制服务 |

**请求体格式：**
```json
{
  "instruction_id": "string",            // 必填，指令唯一 ID
  "device_id": "string",                 // 必填，目标无人机设备 ID
  "target_position": {                   // 必填，目标位置
    "latitude": "float",
    "longitude": "float",
    "altitude": "float"
  },
  "algorithm": "string",                 // 可选，导航算法名称 (默认 "default")
  "parameters": {                        // 可选，算法参数
    "step_count": "int",                 // 航点数量 (默认 10)
    "speed": "float",                    // 速度 m/s (默认 5.0)
    "altitude": "float"                  // 飞行高度 (覆盖 target_position.altitude)
  }
}
```

**请求样例：**
```http
POST http://192.168.1.50:9000/api/v1/navigation/instruction
Content-Type: application/json

{
  "instruction_id": "nav_20240510_001",
  "device_id": "drone_sim_0",
  "target_position": {
    "latitude": 39.91,
    "longitude": 116.42,
    "altitude": 120.0
  },
  "algorithm": "simple_linear",
  "parameters": {
    "step_count": 5,
    "speed": 8.0
  }
}
```

**响应样例：**
```json
{
  "success": true,
  "message": "导航轨迹已生成并上报",
  "data": {
    "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "device_id": "drone_sim_0",
    "waypoints": [
      { "latitude": 39.9042, "longitude": 116.4074, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90536, "longitude": 116.41, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90652, "longitude": 116.4126, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90768, "longitude": 116.4152, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90884, "longitude": 116.4178, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.91, "longitude": 116.42, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} }
    ],
    "algorithm_name": "simple_linear",
    "total_distance": 1287.45,
    "estimated_time": 160.93,
    "metadata": {
      "step_count": 5,
      "parameters": { "step_count": 5, "speed": 8.0 }
    }
  }
}
```

---

### 1.6 轨迹执行

执行已生成的导航轨迹，通过 MAVLink 将航点发送到无人机。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/navigation/execute` |
| **调用方** | 边缘控制服务 |

**请求体格式：**
```json
{
  "trajectory_id": "string"    // 必填，轨迹 ID（从导航指令响应中获取）
}
```

**请求样例：**
```http
POST http://192.168.1.50:9000/api/v1/navigation/execute
Content-Type: application/json

{
  "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**响应样例：**
```json
{
  "success": true,
  "message": "轨迹执行中",
  "data": {
    "success": true,
    "message": "模拟发送 6 个航点到 drone_sim_0",
    "waypoint_count": 6
  }
}
```

**轨迹不存在时的响应：**
```json
{
  "success": false,
  "message": "轨迹 invalid-id 未找到",
  "data": {
    "success": false,
    "error": "轨迹 invalid-id 未找到"
  }
}
```

---

### 1.7 活动轨迹列表

查看所有已生成但仍在活动中的导航轨迹。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/navigation/trajectories` |
| **调用方** | 边缘控制服务 / 监控面板 |
| **请求体** | 无（空 body 或 `{}`） |

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": {
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
      "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "device_id": "drone_sim_0",
      "waypoints": [ ... ],
      "algorithm_name": "simple_linear",
      "total_distance": 1287.45,
      "estimated_time": 160.93,
      "metadata": {}
    }
  }
}
```

---

### 1.8 可用导航算法列表

列出系统中已注册的所有导航算法。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/navigation/algorithms` |
| **请求体** | 无（空 body 或 `{}`） |

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": ["simple_linear"]
}
```

---

### 1.9 系统状态

获取类脑盒子系统整体运行状态。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/system/status` |
| **请求体** | 无（空 body 或 `{}`） |

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": {
    "status": "running",
    "drones": {
      "total": 3,
      "online": 3,
      "offline": 0,
      "devices": [ ... ]
    },
    "algorithms": ["simple_linear"]
  }
}
```

---

### 1.10 已注册通信协议

列出系统中已注册的所有通信协议。

| 项目 | 值 |
|------|-----|
| **路径** | `POST /api/v1/system/protocols` |
| **请求体** | 无（空 body 或 `{}`） |

**响应样例：**
```json
{
  "success": true,
  "message": "",
  "data": ["mavlink"]
}
```

---

## 二、输出接口（类脑盒子 → 边缘控制服务）

这些接口由类脑盒子**主动**向边缘控制服务发送（POST 请求），路径在 `config.yaml` 中配置。

| 接口 | 默认路径 | 触发方式 | 配置项 |
|------|---------|---------|--------|
| 心跳上报 | `/api/v1/brain-box/heartbeat` | 周期 (默认 5s) | `edge.heartbeat_path` |
| 无人机状态上报 | `/api/v1/brain-box/drone-report` | 周期 (默认 2s) | `edge.drone_report_path` |
| 状态变化即时上报 | `/api/v1/brain-box/drone-report` | 事件触发 | `edge.drone_report_path` |
| 导航轨迹上报 | `/api/v1/brain-box/trajectory-report` | 导航指令处理后 | `edge.trajectory_report_path` |

边缘服务 Base URL 配置项：`edge.base_url`（默认 `http://192.168.1.100:8080`）

---

### 2.1 心跳上报

类脑盒子周期性向边缘控制服务发送心跳。

| 项目 | 值 |
|------|-----|
| **目标路径** | `POST {edge.base_url}{edge.heartbeat_path}` |
| **默认** | `POST http://192.168.1.100:8080/api/v1/brain-box/heartbeat` |
| **触发** | 每 `edge.heartbeat_interval` 秒自动发送 (默认 5s) |

**类脑盒子发送的请求体：**
```json
{
  "box_id": "brain_box_001",
  "timestamp": 1715340005.789,
  "status": "running",
  "drone_count": 3,
  "online_count": 3
}
```

**字段说明：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `box_id` | string | 类脑盒子标识 |
| `timestamp` | float | Unix 时间戳 |
| `status` | string | 运行状态 (`running`) |
| `drone_count` | int | 已发现无人机总数 |
| `online_count` | int | 在线无人机数量 |

---

### 2.2 无人机状态上报

类脑盒子周期性向边缘控制服务上报所有无人机状态。

| 项目 | 值 |
|------|-----|
| **目标路径** | `POST {edge.base_url}{edge.drone_report_path}` |
| **默认** | `POST http://192.168.1.100:8080/api/v1/brain-box/drone-report` |
| **触发** | 每 `edge.report_interval` 秒自动发送 (默认 2s)，仅在有设备时发送 |

**类脑盒子发送的请求体：**
```json
{
  "box_id": "brain_box_001",
  "timestamp": 1715340002.456,
  "devices": [
    {
      "device_id": "drone_sim_0",
      "device_type": "quadcopter",
      "protocol": "mavlink",
      "status": "online",
      "ip_address": "127.0.0.1",
      "port": 14550,
      "last_heartbeat": 1715340000.123,
      "position": {
        "latitude": 39.9042,
        "longitude": 116.4074,
        "altitude": 100.0
      },
      "metadata": {
        "autopilot": "simulated",
        "mav_type": "quadrotor",
        "system_status": "active"
      }
    },
    {
      "device_id": "drone_sim_1",
      "device_type": "quadcopter",
      "protocol": "mavlink",
      "status": "online",
      "ip_address": "127.0.0.1",
      "port": 14551,
      "last_heartbeat": 1715340000.456,
      "position": {
        "latitude": 39.9052,
        "longitude": 116.4084,
        "altitude": 110.0
      },
      "metadata": {
        "autopilot": "simulated",
        "mav_type": "quadrotor",
        "system_status": "active"
      }
    }
  ]
}
```

---

### 2.3 无人机状态变化即时上报

当无人机状态发生变化时（如上线/离线），立即向边缘控制服务上报。

| 项目 | 值 |
|------|-----|
| **目标路径** | `POST {edge.base_url}{edge.drone_report_path}` |
| **默认** | `POST http://192.168.1.100:8080/api/v1/brain-box/drone-report` |
| **触发** | 设备状态变化时事件触发 |

**类脑盒子发送的请求体：**
```json
{
  "box_id": "brain_box_001",
  "timestamp": 1715340010.789,
  "event": "status_change",
  "device": {
    "device_id": "drone_sim_0",
    "device_type": "quadcopter",
    "protocol": "mavlink",
    "status": "offline",
    "ip_address": "127.0.0.1",
    "port": 14550,
    "last_heartbeat": 1715339990.123,
    "position": {
      "latitude": 39.9042,
      "longitude": 116.4074,
      "altitude": 100.0
    },
    "metadata": {}
  }
}
```

---

### 2.4 导航轨迹上报

当类脑盒子处理导航指令并生成轨迹后，自动将轨迹上报给边缘控制服务。

| 项目 | 值 |
|------|-----|
| **目标路径** | `POST {edge.base_url}{edge.trajectory_report_path}` |
| **默认** | `POST http://192.168.1.100:8080/api/v1/brain-box/trajectory-report` |
| **触发** | 接收到导航指令并生成轨迹后自动发送 |

**类脑盒子发送的请求体：**
```json
{
  "box_id": "brain_box_001",
  "timestamp": 1715340015.123,
  "trajectory": {
    "trajectory_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "device_id": "drone_sim_0",
    "waypoints": [
      { "latitude": 39.9042, "longitude": 116.4074, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90536, "longitude": 116.41, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90652, "longitude": 116.4126, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90768, "longitude": 116.4152, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.90884, "longitude": 116.4178, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} },
      { "latitude": 39.91, "longitude": 116.42, "altitude": 120.0, "speed": 8.0, "hold_time": 0.0, "metadata": {} }
    ],
    "algorithm_name": "simple_linear",
    "total_distance": 1287.45,
    "estimated_time": 160.93,
    "metadata": {
      "step_count": 5,
      "parameters": { "step_count": 5, "speed": 8.0 }
    }
  }
}
```

---

## 三、统一响应格式

所有类脑盒子 **输入接口** 的响应均使用统一格式：

```json
{
  "success": true,       // bool — 请求是否成功
  "message": "",         // string — 提示信息或错误描述
  "data": null           // any — 响应数据，格式视具体接口而定
}
```

**输出接口**（类脑盒子向边缘服务发送的请求）期望边缘服务返回任意 JSON 响应即可。

---

## 四、数据结构定义

### DeviceInfo — 设备信息

```json
{
  "device_id": "string",            // 设备唯一标识
  "device_type": "string",          // 设备类型 (quadcopter, hexarotor, fixed_wing, ...)
  "protocol": "string",             // 通信协议 (mavlink, ...)
  "status": "string",               // 状态 (online, offline, busy, error, unknown)
  "ip_address": "string",           // IP 地址
  "port": 0,                        // 端口
  "last_heartbeat": 0.0,            // 最后心跳时间 (Unix 时间戳)
  "position": {                     // 位置信息
    "latitude": 0.0,                // 纬度
    "longitude": 0.0,               // 经度
    "altitude": 0.0,                // 海拔高度 (米)
    "relative_alt": 0.0,            // 相对高度 (米, MAVLink 提供)
    "heading": 0.0                  // 航向角 (度, MAVLink 提供)
  },
  "metadata": {}                    // 扩展元数据 (autopilot, mav_type, system_status, ...)
}
```

### Waypoint — 航点

```json
{
  "latitude": 0.0,          // 纬度
  "longitude": 0.0,         // 经度
  "altitude": 0.0,          // 高度 (米)
  "speed": 5.0,             // 速度 (m/s)
  "hold_time": 0.0,         // 悬停时间 (秒)
  "metadata": {}             // 扩展元数据
}
```

### NavigationTrajectory — 导航轨迹

```json
{
  "trajectory_id": "string",       // 轨迹唯一 ID (UUID)
  "device_id": "string",           // 目标设备 ID
  "waypoints": [],                 // 航点列表 (Waypoint[])
  "algorithm_name": "string",      // 使用的算法名称
  "total_distance": 0.0,           // 总距离 (米)
  "estimated_time": 0.0,           // 预计时间 (秒)
  "metadata": {}                   // 扩展元数据
}
```
