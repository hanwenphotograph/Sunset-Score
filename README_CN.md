# SunsetScore

[English](README.md) | [简体中文](README_CN.md)

SunsetScore 是一个跨平台 Python 命令行程序。它按固定间隔从目录中采样照片，使用本地视觉语言模型判断每张采样图片的晚霞视觉特征，最后输出平均分和最高分。

评分是模型生成的置信指数，不是经过统计校准的真实概率。程序只判断可见画面，不使用 EXIF 时间或拍摄地点，因此视觉上相似的朝霞也可能获得高分。

## 功能

- 首次下载模型后完全在本地运行，无需 API 密钥或云服务
- 按相对路径和文件名自然排序，执行确定性采样
- 使用 `-r` / `--recursive` 扫描完整目录树
- 读取输入目录中的严格 TOML 配置
- 打印进度、逐张分数、判分理由和耗时
- 日志写入标准错误，汇总结论写入标准输出
- 支持面向用户的文本输出和面向程序的 JSON 输出
- 提供只返回平均分和最高分的 Python API
- 单张图片不可读时跳过，其他样本仍可继续评分

## 运行要求

- Python 3.10 或更高版本
- Windows 10/11 x64
- Intel 或 Apple Silicon Mac
- 主流 Linux x64 发行版
- 约 1.6 GB 模型与运行时磁盘空间
- JPG、JPEG 或 PNG 输入图片

首版不支持 32 位系统、Linux ARM、RAW、HEIC、AVIF 或可配置的 GPU 专用加速。

## 安装

### 使用 pipx 从 GitHub 安装

推荐使用 `pipx`，它会创建隔离环境并提供全局 `sunsetscore` 命令：

```console
pipx install "git+https://github.com/hanwenphotograph/Sunset-Score.git"
```

### 安装到当前 Python 环境

```console
python -m pip install "git+https://github.com/hanwenphotograph/Sunset-Score.git"
```

### 从本地仓库安装

```console
git clone https://github.com/hanwenphotograph/Sunset-Score.git
cd Sunset-Score
python -m pip install .
```

安装后验证命令：

```console
sunsetscore --version
sunsetscore --help
```

不提供输入目录时，`sunsetscore` 只打印帮助，不加载或下载模型。

## 快速使用

评分目录第一层中的受支持图片：

```console
sunsetscore /path/to/photos
```

递归扫描所有子目录：

```console
sunsetscore -r /path/to/photos
```

临时覆盖采样间隔并输出机器可读结果：

```console
sunsetscore /path/to/photos --interval 5 --json
```

文本输出：

```text
平均分: 68.40
最高分: 93
```

JSON 输出：

```json
{"average_score":68.4,"max_score":93}
```

运行日志始终写入标准错误，最终文本或 JSON 结论写入标准输出，因此外部调用方无需解析日志即可捕获结果。

## 采样规则

SunsetScore 按大小写不敏感的自然顺序排列受支持图片，例如 `photo2.jpg` 位于 `photo10.jpg` 之前。

默认间隔为 `10`，对应采样位置 `1、11、21、31...`。目录中不足十张受支持图片时仍会采样第一张。递归模式会先把所有发现的图片合并为一个全局排序序列，再执行采样。

图片符号链接、目录符号链接和 Windows 重解析目录会被忽略，不受支持的文件格式不会进入采样序列。

## 本地配置

在输入目录根部创建 `.sunsetscore.toml`：

```toml
[sampling]
interval = 10
```

配置采用严格校验。未知字段、错误类型或小于 `1` 的间隔会终止运行并报告错误。优先级从低到高依次为内置默认值、本地配置和命令行 `--interval`。

## 模型与托管运行时

首次实际评分时，程序会自动下载并校验以下固定组件：

- 当前平台对应的 `llama.cpp b10040` 便携运行时，约 11-18 MB
- `Qwen3-VL-2B-Instruct Q4_K_M` 主模型，约 1.11 GB
- `Qwen3-VL-2B-Instruct Q8_0` 视觉投影，约 445 MB

下载过程支持进度日志、临时文件、HTTP 断点续传、SHA-256 校验、原子安装和一次自动重试。之后可以完全离线运行，但程序仍会检查缓存模型的完整性。

托管文件默认存放在操作系统标准的 SunsetScore 用户数据目录中。设置 `SUNSETSCORE_HOME` 可以改用其他位置，也可以把它放在便携安装目录旁：

```powershell
$env:SUNSETSCORE_HOME = "D:\Apps\SunsetScoreData"
sunsetscore D:\Photos
```

```bash
export SUNSETSCORE_HOME="$HOME/apps/sunsetscore-data"
sunsetscore ~/Pictures
```

模型权重来自 [Qwen 官方 GGUF 仓库](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF)，推理运行时来自 [llama.cpp](https://github.com/ggml-org/llama.cpp)。

## 分数含义

固定提示词向模型提供以下预期区间：

- `0-10`：没有可见天空，或完全没有晚霞证据
- `11-20`：只有蓝色、灰色或黑色天空，没有有效暖色霞光
- `21-49`：存在有限暖色，但仍可能来自普通光照或滤镜
- `50-74`：天空中存在清晰可见的暖色霞光
- `75-94`：明显而强烈的晚霞色彩，或云层受到霞光照亮
- `95-100`：大面积、强烈且毫无歧义的晚霞

这些区间描述的是要求模型遵循的评分准则，但小型生成式视觉语言模型不一定始终严格遵守每个数字边界。建议把分数视为粗粒度排序信号，并在用于自动决策前使用自己的照片验证阈值。对于长时间序列，最高分通常更适合判断其中是否出现过晚霞，平均分则容易被大量普通画面稀释。

## 性能

在开发电脑上，本地 CPU 对每张采样图片的推理耗时约为 12-13 秒。实际速度取决于 CPU、内存带宽、图片内容和操作系统。

可以使用以下公式估算耗时：

```text
运行时间 ≈ ceil(图片数量 / 采样间隔) × 单张推理耗时
```

例如，约 1,800 张图片在默认间隔 `10` 下会产生约 180 次推理，在开发电脑上需要约 36-39 分钟。首次运行还需要下载约 1.55 GB 模型数据。

## Python API

Python 调用方可以直接取得汇总结论：

```python
from sunsetscore import score_directory

result = score_directory("D:/Photos", recursive=True, interval=10)
print(result.average_score)
print(result.max_score)
```

`ScoreResult` 只公开 `average_score` 和 `max_score`。单张评分、模型理由、成功数量和失败数量会写入运行日志。

损坏或无法读取的采样图片会被记录并跳过，不会自动选择下一张补位。只要至少一张样本评分成功，运行就会生成结论。没有匹配图片或所有样本均失败时，程序返回非零退出码且不输出伪造分数。

## 开发

```console
python -m pip install -e ".[test]"
python -m pytest
```

自动化测试默认使用本地替身，不会下载大型模型。真实模型与运行时只会在第一次实际评分时安装到程序数据目录。
