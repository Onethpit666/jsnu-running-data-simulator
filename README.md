# JSNU Running Data Simulator

基于 Python、Flask、参数化跑道模型和随机过程的跑步数据仿真及 FIT/TCX 导出系统。

## 功能

- 自定义距离、配速、开始时间、采样间隔和跑道形状。
- 模拟配速变化、末段加速趋势及平滑变道。
- 可选不规则心率、步频、功率、步幅、高度、消耗及本地负荷估算。
- 用暂停事件区分训练时长与总时长，默认暂停 3 秒。
- 网页预览轨迹、统计及配速/心率曲线；支持单条 FIT/TCX 和批量 ZIP。

所有轨迹与运动指标均为模拟/估算，用于学习和文件兼容性测试，不是实测数据。
用户实测表明安卓 Keep 可以读取 FIT 的心率、步频、功率、高度及训练/总时长；具体字段是否展示取决于接收应用。
本地 session-RPE 负荷估算不等于 Keep 自身算法；平均步幅的 Keep 展示尚未确认。

## 安装与启动

Python 3.10 或更新版本：

```sh
python -m pip install -r requirements.txt
python app.py
```

网页默认为 http://127.0.0.1:5000 。仅监听本机，控制台按 Ctrl+C 退出。
Windows 也可先运行 install.bat，再运行 start.bat。
端口冲突时使用 python app.py --port 5001 。

## 位置与隐私

公开副本的默认纬度、经度均为 0，角度为 0°，仅作为几何示例。
使用前在网页中填写所需 WGS84 跑道中心及顺时针旋转角度；轨迹预览是相对坐标，不是在线地图。
此副本不包含用户实际位置配置、运动记录、截图、虚拟环境、缓存或打包程序。
示例和测试使用固定的虚构日期 2020-01-01，不代表用户活动时间。
生成的 FIT、TCX、ZIP、样本目录和本地设置已列入 .gitignore；仍需在每次提交前检查文件。

## 数据模型

单圈几何长度为 2×直道长度 + 2π×弯道半径。距离由采样坐标累计计算；平均配速按训练时间归一化。
变化编号与开始时间决定随机种子，同样的输入生成同样的文件。
心率包含热身趋势、对配速变化的滞后响应和短期关联随机波动。参数不代表任何人群的健康标准。
步幅由速度与步频推导；消耗粗估为体重乘距离公里数；负荷估算为训练分钟数乘主观强度。
平坦跑道默认爬升 0，非零高度是模拟曲线。
TCX 的部分数据使用 Garmin ActivityExtension/v2，应用可能忽略；FIT 使用原生字段与 timer 事件。

## 测试、示例与构建

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python example.py
```

example.py 会在本机生成 samples/synthetic_2km.tcx，此目录不会纳入 Git。
官方 TCX XSD 校验需设置 TCX_SCHEMA 为 TrainingCenterDatabasev2.xsd 的路径，并在同目录保存 ActivityExtensionv2.xsd。
未设置时跳过 XSD 检查。FIT 校验通过 Garmin SDK 解码及 CRC 检查。

本地构建 Windows 程序：运行 build.bat，产物为 dist/KeepRunStudio.exe。
公开源码副本不包含 EXE；发布包含第三方 SDK 的二进制前需确认其再分发条件。

## 结构

```text
app.py                 本机服务、接口与下载
config.py              默认参数及资源限制
services/activity.py   参数校验、几何、采样与统计
services/metrics.py    关联指标和心率模拟
services/tcx.py        TCX 写入
services/fit.py        FIT 编码
templates/            网页结构
static/               本地样式及交互
tests/                验证
example.py            命令行示例
```

## 来源与许可

本项目基于 jsnu-lepao-system-main 整理和扩展。发布者应补充原仓库链接及作者信息。
收到的原项目没有 LICENSE 文件，原项目再发布授权尚需确认；本副本没有擅自添加 MIT 等许可证。
Garmin FIT SDK 使用专门的 FIT Protocol License Agreement，见 Garmin-FIT-LICENSE.txt 及 https://github.com/garmin/fit-python-sdk 。
SDK 通过 requirements.txt 安装，不随本仓库直接附带其源代码或二进制。第三方依赖不随本项目改换许可证。
公开源码与取得完整开源授权是不同事项，发布前需补齐原项目授权及自己的许可声明。
