# BrainBox 类脑盒子服务器

无人机管控与导航系统 — 连接边缘控制服务和无人机群，提供导航轨迹生成与任务执行。

## 架构

```
┌────────────────┐     HTTP/POST     ┌──────────────┐     MAVLink      ┌──────────┐
│  边缘控制服务   │ ◄──────────────► │  类脑盒子     │ ◄──────────────► │  无人机   │
│  Edge Server   │                   │  BrainBox    │                   │  Drones  │
└────────────────┘                   └──────────────┘                   └──────────┘
```

### 低耦合设计

- **通信协议注册中心** (`ProtocolRegistry`): 支持动态注册 MAVLink、串口、CAN 等通信协议
- **导航算法注册中心** (`AlgorithmRegistry`): 支持动态注册 A*、RRT、直线导航等算法
- **设备抽象接口** (`DeviceProtocol`): 统一设备通信接口，与具体协议解耦
- **算法抽象接口** (`NavigationAlgorithm`): 统一算法接口，与具体实现解耦

### 模块结构

```
brain_box/
├── config/           # 配置管理 (YAML + 环境变量)
├── core/             # 核心抽象接口 (设备、算法)
├── communication/    # 通信协议层 (MAVLink 等, 可扩展)
├── drone/            # 无人机管理器
├── navigation/       # 导航模块 (算法注册, 轨迹生成)
├── edge/             # 边缘服务通信 (HTTP 客户端, 上报器)
├── api/              # HTTP API (全部 POST)
├── logging_config/   # 日志配置
└── main.py           # 入口
```

## 快速开始

### 安装

```bash
pip install -e .
```

安装 MAVLink 支持 (可选):

```bash
pip install -e ".[mavlink]"
```

### 配置

编辑 `config.yaml` 或通过环境变量覆盖:

```bash
export BRAIN_BOX_EDGE_URL="http://10.0.0.1:8080"
export BRAIN_BOX_SERVER_PORT=9000
export BRAIN_BOX_LOG_LEVEL=DEBUG
```

### 运行

```bash
brain-box                        # 使用默认配置
brain-box -c /path/to/config.yaml  # 指定配置文件
brain-box --host 0.0.0.0 --port 9000
```

## API 接口

所有接口使用 **POST** 方法。

### 无人机管理

| 路径 | 说明 |
|------|------|
| `/api/v1/drones/scan` | 扫描网络中的无人机 |
| `/api/v1/drones/query` | 查询无人机信息 |
| `/api/v1/drones/summary` | 获取无人机汇总 |
| `/api/v1/drones/command` | 发送控制指令 |

### 导航

| 路径 | 说明 |
|------|------|
| `/api/v1/navigation/instruction` | 接收导航指令，生成轨迹 |
| `/api/v1/navigation/execute` | 执行导航轨迹 |
| `/api/v1/navigation/trajectories` | 查看活动轨迹 |
| `/api/v1/navigation/algorithms` | 列出可用算法 |

### 系统

| 路径 | 说明 |
|------|------|
| `/api/v1/system/status` | 系统状态 |
| `/api/v1/system/protocols` | 已注册通信协议 |

## 扩展

### 添加新通信协议

```python
from brain_box.core.device import DeviceProtocol, DeviceInfo

class MyProtocol(DeviceProtocol):
    @property
    def protocol_name(self) -> str:
        return "my_protocol"

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def scan_devices(self) -> list[DeviceInfo]: ...
    async def send_command(self, device_id, command) -> dict: ...
    async def get_device_status(self, device_id) -> DeviceInfo | None: ...

# 注册到系统
protocol_registry.register(MyProtocol())
```

### 添加新导航算法

```python
from brain_box.core.algorithm import NavigationAlgorithm, NavigationTrajectory

class MyAlgorithm(NavigationAlgorithm):
    @property
    def algorithm_name(self) -> str:
        return "my_algorithm"

    async def generate_trajectory(self, device_id, current_position,
                                   target_position, parameters=None) -> NavigationTrajectory:
        ...

# 注册到系统
algorithm_registry.register(MyAlgorithm())
```

## 开发

```bash
pip install -e ".[dev]"
pytest
ruff check brain_box/ tests/
mypy brain_box/
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BRAIN_BOX_CONFIG` | 配置文件路径 | `config.yaml` |
| `BRAIN_BOX_EDGE_URL` | 边缘服务地址 | `http://192.168.1.100:8080` |
| `BRAIN_BOX_EDGE_HEARTBEAT_PATH` | 心跳上报路径 | `/api/v1/brain-box/heartbeat` |
| `BRAIN_BOX_EDGE_DRONE_REPORT_PATH` | 无人机上报路径 | `/api/v1/brain-box/drone-report` |
| `BRAIN_BOX_EDGE_TRAJECTORY_REPORT_PATH` | 轨迹上报路径 | `/api/v1/brain-box/trajectory-report` |
| `BRAIN_BOX_MAVLINK_CONNECTION` | MAVLink 连接串 | `udpin:0.0.0.0:14550` |
| `BRAIN_BOX_SERVER_HOST` | 服务监听地址 | `0.0.0.0` |
| `BRAIN_BOX_SERVER_PORT` | 服务监听端口 | `9000` |
| `BRAIN_BOX_LOG_LEVEL` | 日志级别 | `INFO` |
| `BRAIN_BOX_LOG_DIR` | 日志目录 | `logs` |
