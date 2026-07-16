# SunsetScore

SunsetScore 是一个跨平台 Python 命令行程序。它按固定间隔采样目录中的照片，使用本地视觉语言模型计算每张采样照片的晚霞指数，最后输出平均分和最高分。

评分是可重复、可比较的模型置信指数，不是经过统计校准的真实概率。程序只判断画面是否具有典型晚霞视觉特征，不使用 EXIF 时间或拍摄地点，因此视觉相似的朝霞也可能获得高分。

## 支持范围

- Python 3.10 及以上版本
- Windows 10/11 x64
- macOS Intel 与 Apple Silicon
- 主流 Linux x64 发行版
- JPG、JPEG 和 PNG 图片，扩展名大小写不敏感

首版不支持 32 位系统、Linux ARM、RAW、HEIC、AVIF 或 GPU 专用加速配置。

## 安装

推荐使用 `pipx` 安装，以便自动创建隔离环境并提供全局命令：

```console
pipx install .
```

也可以安装到当前 Python 环境：

```console
python -m pip install .
```

安装后可直接运行：

```console
sunsetscore --help
```

不提供输入目录时，程序只打印完整帮助，不加载或下载模型。

## 使用

评分当前目录中的照片：

```console
sunsetscore .
```

递归扫描所有子目录：

```console
sunsetscore -r D:\Photos\Sunsets
```

临时覆盖采样间隔并输出机器可读结果：

```console
sunsetscore D:\Photos --interval 5 --json
```

默认文本结果如下：

```text
平均分: 68.40
最高分: 93
```

`--json` 结果只包含结论：

```json
{"average_score":68.4,"max_score":93}
```

运行日志始终写入标准错误，最终文本或 JSON 结论写入标准输出。外部调用方可以单独捕获标准输出，而无需解析日志。

## 采样规则

程序按相对路径和文件名进行大小写不敏感的自然排序，例如 `photo2.jpg` 位于 `photo10.jpg` 之前。

默认选择排序后的第 `1、11、21、31...` 张照片。即使目录中不足 10 张照片，也会评分第一张照片。递归模式将所有子目录中的照片合并为一个全局序列后再采样。

符号链接文件、符号链接目录和 Windows 重解析目录不会被扫描。

## 本地配置

在输入目录根部创建 `.sunsetscore.toml`：

```toml
[sampling]
interval = 10
```

配置文件采用严格校验。未知字段、错误类型或小于 1 的间隔会直接导致运行失败。优先级从低到高为：内置默认值、本地配置、命令行 `--interval`。

## 模型与首次运行

首次实际评分时，程序会自动下载并校验以下固定组件：

- `llama.cpp b10040` 的目标平台便携运行包，约 11-18 MB
- `Qwen3-VL-2B-Instruct Q4_K_M` 主模型，约 1.11 GB
- `Qwen3-VL-2B-Instruct Q8_0` 视觉投影，约 445 MB

下载支持进度显示、临时文件、断点续传、SHA-256 校验和一次自动重试。之后可完全离线运行，但每次启动仍会校验固定模型文件。

组件默认存放在操作系统的 SunsetScore 用户数据目录中。设置 `SUNSETSCORE_HOME` 可以改为程序旁边或其他位置：

```powershell
$env:SUNSETSCORE_HOME = "D:\Apps\SunsetScoreData"
sunsetscore D:\Photos
```

```bash
export SUNSETSCORE_HOME="$HOME/apps/sunsetscore-data"
sunsetscore ~/Pictures
```

模型来源为 [Qwen 官方 GGUF 仓库](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF)，推理运行时来源为 [llama.cpp](https://github.com/ggml-org/llama.cpp)。

## Python API

Python 调用方可以直接取得结构化结论：

```python
from sunsetscore import score_directory

result = score_directory("D:/Photos", recursive=True, interval=10)
print(result.average_score)
print(result.max_score)
```

`ScoreResult` 只公开 `average_score` 和 `max_score`。单张评分、模型理由、成功数量与失败数量只写入运行日志。

损坏或无法读取的采样图片会被记录并跳过，不会自动选择下一张补位。只要至少一张采样图片评分成功，程序就会基于成功结果生成结论；如果没有匹配图片或所有样本失败，则返回非零退出码且不输出伪造分数。

## 开发

```console
python -m pip install -e ".[test]"
python -m pytest
```

测试默认使用本地替身，不会下载大型模型。真实模型与运行时只在第一次实际评分时安装到程序数据目录。
