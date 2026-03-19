# WiFi Analyzer - WiFi 网络分析工具

## 概述

基于 Python + tkinter 的 Windows WiFi 网络分析器，通过调用 `netsh wlan show networks` 扫描周围 WiFi 网络，以图形化界面展示网络信息、信号强度和信道分布。

## 技术栈

| 项目 | 说明 |
|------|------|
| 语言 | Python 3.12 |
| GUI | tkinter（标准库） |
| 数据源 | Windows `netsh wlan show networks mode=bssid` |
| 打包 | PyInstaller（单文件 exe） |
| 图标 | dragon.ico |

## 功能特性

### 1. 网络列表

- 表格展示所有扫描到的 WiFi 接入点
- 字段：SSID、信号强度(%)、dBm、信道、频段、安全类型、BSSID
- 点击列头排序（信号/信道等）
- 颜色区分信号强弱：绿色(>=60%)、橙色(>=35%)、红色(<35%)

### 2. 信号强度图

- 横向柱状图，按信号从高到低排列
- 左侧完整显示 SSID 名称
- 右侧标注百分比和 dBm 值
- 柱子颜色根据信号强度渐变（绿/黄绿/橙/红）

### 3. 信道分布图

- 2.4 GHz（CH 1-13）和 5 GHz（CH 36-165）分区展示所有标准信道
- **Y 轴为信号强度(0-100%)**，每个 WiFi 网络独立显示柱子
- 同一信道上多个网络并排显示，高度代表各自信号强度
- 每个 SSID 使用不同颜色（10 色调色板），柱顶标注 SSID 名称和信号百分比
- 空闲信道用浅灰细条标识，便于发现最佳信道
- 鼠标悬停柱子弹出 Tooltip，显示完整网络详情

### 4. 界面设计

- 浅色清爽风格（白色背景 + 蓝色强调色）
- 自定义无边框标题栏，支持鼠标拖动
- 右上角红色 X 关闭按钮（悬停变色）
- 标题栏集成所有控件：扫描按钮、自动刷新开关、刷新间隔选择、状态文字

### 5. 扫描控制

- 手动扫描按钮
- 自动刷新：支持 1s / 3s / 5s / 10s 间隔切换
- 多线程扫描，不阻塞 UI

## 文件结构

```
ticket2/
├── wifi_analyzer.py      # 主程序源码
├── dragon.ico            # 应用图标
├── WiFiAnalyzer.md       # 本文档
├── dist/
│   └── WiFiAnalyzer.exe  # 打包后的可执行文件（11MB）
├── build/                # PyInstaller 构建临时文件
└── WiFiAnalyzer.spec     # PyInstaller 配置文件
```

## 运行方式

### 源码运行

```bash
python wifi_analyzer.py
```

无需安装额外依赖，仅使用 Python 标准库。

### EXE 运行

直接双击 `dist/WiFiAnalyzer.exe`，无需 Python 环境。

### 重新打包

```bash
pyinstaller --onefile --windowed --icon=dragon.ico --add-data "dragon.ico;." --name "WiFiAnalyzer" wifi_analyzer.py
```

## 核心实现

### 数据采集

调用 `netsh wlan show networks mode=bssid` 获取原始输出，自动检测编码（UTF-8 优先，回退 GBK），解析以下字段：

- SSID、BSSID（正则提取 MAC 地址）
- 身份验证 / Authentication
- 加密 / Encryption
- 信号强度（百分比，换算 dBm）
- 频道（排除"频道利用率"干扰）
- 波段（2.4 GHz / 5 GHz）

### 编码兼容

不同 Windows 版本 `netsh` 输出编码不同（中文 Windows 可能是 UTF-8 或 GBK），程序先尝试 UTF-8 解码，失败后回退 GBK。

### PyInstaller 兼容

图标路径通过 `sys._MEIPASS` 兼容打包环境，`--add-data` 将 `dragon.ico` 打入 exe。

## 信号强度参考

| 信号(%) | dBm | 质量 |
|---------|-----|------|
| 75-100% | -63 ~ -50 | 优秀 |
| 50-74%  | -75 ~ -64 | 良好 |
| 30-49%  | -85 ~ -76 | 一般 |
| <30%    | < -85     | 较差 |
