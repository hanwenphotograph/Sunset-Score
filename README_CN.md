# SunsetScore

[English](README.md) | [简体中文](README_CN.md)

SunsetScore 是一个跨平台 Python 命令行程序。它按固定间隔从目录中采样照片，使用本地视觉语言模型判断每张采样图片的晚霞视觉特征，最后输出是否检测到晚霞及其照片区间。

评分是模型生成的置信指数，不是经过统计校准的真实概率。程序只判断可见画面，不使用 EXIF 时间或拍摄地点，因此视觉上相似的朝霞也可能获得高分。

## 功能

- 首次下载模型后完全在本地运行，无需 API 密钥或云服务
- 自动使用兼容 GPU，并支持强制 CPU 与失败自动回退
- 复用单个本地推理服务，在不复制模型进程的前提下并发处理最多两个请求
- 按相对路径和文件名自然排序，执行确定性采样
- 使用 `-r` / `--recursive` 扫描完整目录树
- 可将每个合法后代目录分别分析并生成 Markdown 报告
- 使用 `--autopack` 将完整晚霞区间复制到受管理的 `SunsetResult` 目录
- 持久化成功的目录评分，并在后续运行中自动复用
- 读取输入目录中的严格 TOML 配置
- 打印进度、逐张分数、判分理由和耗时
- 日志写入标准错误，汇总结论写入标准输出
- 支持面向用户的文本输出和面向程序的 JSON 输出
- 提供返回布尔判定和照片区间的 Python API
- 单张图片不可读时跳过，其他样本仍可继续评分

## 运行要求

- Python 3.10 或更高版本
- Windows 10/11 x64
- Intel 或 Apple Silicon Mac
- 主流 Linux x64 发行版
- 仅使用 CPU 时约需 1.6 GB，使用托管 CUDA 文件时约需 3.2 GB
- JPG、JPEG 或 PNG 输入图片

SunsetScore 可以在 Windows 上使用受支持 NVIDIA GPU 的 CUDA 后端，在 macOS 上使用 Metal，并在 Windows 或 Linux 上使用受支持 GPU 的 Vulkan 后端。程序不支持 32 位系统、Linux ARM、RAW、HEIC 或 AVIF。

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

分别分析每个合法后代目录并生成报告：

```console
sunsetscore -r --independently /path/to/photos
```

也可以使用较短的 `-ind` 别名：

```console
sunsetscore -r -ind /path/to/photos
```

临时覆盖采样间隔并输出机器可读结果：

```console
sunsetscore /path/to/photos --interval 5 --json
```

即使目录中已有评分文件也强制重新评分：

```console
sunsetscore /path/to/photos --force
```

将晚霞区间内的所有原始照片复制到 `SunsetResult`：

```console
sunsetscore /path/to/photos --autopack
sunsetscore -r -ind /path/to/photo-sessions --autopack
```

即使存在兼容 GPU 也强制使用 CPU 推理：

```console
sunsetscore /path/to/photos --cpu-infer
```

限制共享 GPU 服务槽位、调度显存预算，或同时限制两者：

```console
sunsetscore /path/to/photos --gpu-workers 2
sunsetscore /path/to/photos --gpu-memory-limit 6
sunsetscore /path/to/photos --gpu-workers 2 --gpu-memory-limit 10
```

文本输出：

```text
平均分: 68.40
最高分: 93
检测到晚霞: 是
晚霞区间: photo101.jpg 至 photo131.jpg
```

JSON 输出：

```json
{"average_score":68.4,"max_score":93,"has_sunset":true,"sunset_ranges":[{"start_photo":"photo101.jpg","end_photo":"photo131.jpg"}]}
```

运行日志始终写入标准错误，最终文本或 JSON 结论写入标准输出，因此外部调用方无需解析日志即可捕获结果。

## 采样规则

SunsetScore 按大小写不敏感的自然顺序排列受支持图片，例如 `photo2.jpg` 位于 `photo10.jpg` 之前。

默认间隔为 `10`，对应采样位置 `1、11、21、31...`。目录中不足十张受支持图片时仍会采样第一张。递归模式会先把所有发现的图片合并为一个全局排序序列，再执行采样。

图片符号链接、目录符号链接和 Windows 重解析目录会被忽略，不受支持的文件格式不会进入采样序列。

## 独立目录分析

`--independently` / `-ind` 只能与 `-r` / `--recursive` 一起使用。此模式会递归查找每个直接包含至少一张受支持图片的后代目录，并把每个目录视为一个独立序列进行分析。

- 输入根目录直接包含的图片不参与分析
- 每个后代目录只处理自己直接包含的图片
- 空目录和只包含不受支持文件的目录会被忽略
- 每个目录读取自己的 `.sunsetscore.toml`
- 命令行 `--interval` 会覆盖所有目录的本地配置
- 单个目录失败会被记录，不会丢弃其他成功目录的结果

执行了新推理的运行结束后，CLI 会打印所有目录的结论，并在输入根目录下写入报告：

```text
sunsetscore-analysis-YYYYMMDD-HHMMSS.md
```

报告包含模型、推理后端、设备、推理槽位与显存限制元数据，以及图片与采样数量、布尔判定、晚霞区间、平均分、最高分、状态和失败详情。新报告不会覆盖已有文件。仅使用兼容缓存的运行会复用最新报告而不生成重复 MD；没有可复用报告时才会新建。只要新推理中存在失败目录，报告仍会生成，但进程会返回非零状态以表示结果不完整。配合 `--json` 时，标准输出包含完整目录结果数组和报告路径。

## 自动打包

`--autopack` 会在输入目录下创建 `SunsetResult`。对于每个晚霞区间，SunsetScore 按自然排序复制从起点到终点之间的全部受支持原始照片，而不只是作为区间端点的采样照片。

直接目录模式把照片写入 `SunsetResult` 第一层。递归单目录模式保留照片相对于输入目录的路径。独立目录模式还会在 `SunsetResult` 下保留每个来源目录，因此不同拍摄任务中的同名照片不会相互覆盖。

`SunsetResult` 完全由 SunsetScore 管理。每次成功打包都会先创建临时目录，再整体替换旧结果，因此过期照片会被清除，而复制失败时旧结果仍然保留。请勿在其中存放需要手动维护的文件。后续递归扫描会排除该目录。

程序会自动复用兼容的评分缓存，因此 `--autopack` 可以直接打包之前的推理结果而不重新加载模型。照片或评分输入发生变化时，请组合使用 `--force --autopack`。纯缓存独立目录运行也会复用最新的 Markdown 报告。该参数本身不会在输入根目录创建 JSON；`--json` 仍然只向标准输出写入结果。

## 评分文件

目录成功完成评分后，SunsetScore 会在该目录内写入以下 JSON 文件：

```text
.sunsetscore-score.json
```

普通或递归的单目录评分会在输入目录中写入该文件。独立目录模式会在每个成功评分的后代目录中分别写入一个文件，评分失败的目录不会生成评分文件。

后续运行的递归范围相同时，SunsetScore 会读取该文件，并跳过模型初始化和推理。缓存会记录 SunsetScore 应用版本、有序采样位置、相对照片路径、分数和理由。来自其他应用版本的缓存会被忽略，并在成功评分后原子替换。使用 `-f` / `--force` 可以刷新同版本缓存。照片、采样配置、命令行间隔或模型发生变化时，同版本缓存不会因此自动失效；需要让这些变化影响结果时，请使用 `--force`。无效或不受支持的评分文件也会被忽略，并在成功评分后替换。

## 本地配置

在输入目录根部创建 `.sunsetscore.toml`：

```toml
[sampling]
interval = 10
```

配置采用严格校验。未知字段、错误类型或小于 `1` 的间隔会终止运行并报告错误。优先级从低到高依次为内置默认值、本地配置和命令行 `--interval`。

## 模型与托管运行时

首次实际评分时，程序会先自动探测可用的加速后端，再下载并校验以下固定组件：

- 所选后端对应的 `llama.cpp b10040` 运行时，下载量约 11-640 MB
- `Qwen3-VL-2B-Instruct Q4_K_M` 主模型，约 1.11 GB
- `Qwen3-VL-2B-Instruct Q8_0` 视觉投影，约 445 MB

后端选择优先级与适用范围如下：

1. Windows x64 检测到兼容 NVIDIA 驱动时使用 CUDA 12.4
2. macOS 使用 Metal
3. Windows 或 Linux 存在 Vulkan 加载器时使用 Vulkan
4. 所有受支持平台最终均可使用 CPU

程序会先让 GPU 运行时列出实际计算设备，通过自检后才会选用该后端。SunsetScore 只启动一个仅监听回环地址的 `llama-server`，模型只加载一次，并将并发图片请求提交到共享服务槽位。实际 GPU 推理随后失败时，程序会停止该服务、记录原因并启动 CPU 服务。`--cpu-infer` 会跳过 GPU 探测并强制使用 CPU。不同后端共用模型文件，但分别缓存各自的托管运行时。

当批次包含多张采样图片时，自动调度会从当前空闲显存中为多模态投影预留 6 GiB，按每个额外请求槽位 4 GiB 估算，且最多使用两个共享槽位。显存容量未知时只使用一个槽位。`--gpu-workers` 接受 `1` 或 `2`，用于设置槽位上限。`--gpu-memory-limit` 用于设置 GiB 为单位的调度预算，最小值为 `3`；它仍是估算值，不是由显卡驱动强制执行的显存硬上限。空闲显存未知或低于 6 GiB 安全余量时，视觉投影器会转到 CPU，而语言模型层仍可使用 GPU。输入图片最长边与动态视觉 token 都限制为 `1024`。GPU 限制参数不能与 `--cpu-infer` 同时使用。

下载过程支持进度日志、临时文件、HTTP 断点续传、SHA-256 校验、原子安装和一次自动重试。之后可以完全离线运行，但程序仍会检查缓存模型的完整性。

SunsetScore 收到可捕获的终止信号时会停止推理服务并有序退出，同时自动清理未完成下载、运行时安装、标准化图片、安装锁和报告临时数据；已校验的模型与已安装运行时会继续保留。操作系统强制结束进程时无法执行进程内清理。

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

这些区间描述的是要求模型遵循的评分准则，但小型生成式视觉语言模型不一定始终严格遵守每个数字边界。建议把分数视为粗粒度信号，并在用于自动决策前使用自己的照片验证判定规则。

## 晚霞判定

分数大于等于 `50` 的采样照片属于高分照片。采样位置不少于三个时，只要任意连续三个位置中至少存在两张高分照片，SunsetScore 就返回 `has_sunset = true`。该规则能够排除孤立高分，同时不会让长序列中短暂出现的晚霞被全片平均分稀释。采样位置不足三个时，任意一张高分照片都会产生肯定结果。

只有参与有效窗口的高分照片才会进入 `sunset_ranges`。相邻的有效采样位置合并成一个包含端点的区间，低分或评分失败的位置会拆分区间。每个端点都是相对于输入目录的照片路径；在非递归和独立目录模式下，它就是照片名。平均分和最高分继续作为兼容与诊断字段提供，但不参与布尔判定。

## 性能

常驻服务消除了逐张加载模型的开销，并在所有请求之间共享模型权重、视觉投影器和 CUDA 上下文。16 GiB 显卡通常会自动选择两个槽位，`--gpu-workers 1` 则提供最保守的运行模式。实际吞吐取决于图片复杂度、推理后端以及视觉投影器能否留在 GPU 上。

可以使用以下公式估算耗时：

```text
采样数 ≈ ceil(图片数量 / 采样间隔)
运行时间 ≈ ceil(采样数 / 并发槽位数) × 并发批次耗时
```

例如，约 1,800 张图片在默认间隔 `10` 下会产生约 180 次推理，在开发电脑上使用 CPU 推理需要约 36-39 分钟。首次运行还需要下载约 1.55 GB 模型数据以及所选运行时。

## Python API

Python 调用方可以直接取得汇总结论：

```python
from sunsetscore import score_directories_independently, score_directory

result = score_directory("D:/Photos", recursive=True, interval=10)
print(result.has_sunset)
for sunset_range in result.sunset_ranges:
    print(sunset_range.start_photo, sunset_range.end_photo)
print(result.average_score)
print(result.max_score)

batch = score_directories_independently("D:/Photo-Sessions", interval=10)
print(batch.report_path)
print(batch.inference_backend, batch.inference_device)
print(batch.inference_workers, batch.gpu_memory_limit_gib)
for directory in batch.directories:
    print(directory.directory, directory.has_sunset, directory.sunset_ranges)

cpu_result = score_directory("D:/Photos", cpu_infer=True)
limited = score_directory(
    "D:/Photos",
    gpu_workers=2,
    gpu_memory_limit=10,
)
refreshed = score_directory("D:/Photos", force=True)
```

两个公开评分函数都默认复用兼容的评分文件，并可通过 `force=True` 刷新结果。`ScoreResult` 公开 `has_sunset`、`sunset_ranges`、`average_score` 和 `max_score`。有序单张评分与模型理由会保存在带版本的评分文件中，并写入运行日志。

损坏或无法读取的采样图片会被记录并跳过，不会自动选择下一张补位。只要至少一张样本评分成功，运行就会生成结论。没有匹配图片或所有样本均失败时，程序返回非零退出码且不输出伪造分数。

## 开发

```console
python -m pip install -e ".[test]"
python -m pytest
```

自动化测试默认使用本地替身，不会下载大型模型。真实模型与运行时只会在第一次实际评分时安装到程序数据目录。
