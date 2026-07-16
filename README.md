# SunsetScore

[English](README.md) | [简体中文](README_CN.md)

SunsetScore is a cross-platform Python CLI that samples photos from a directory, scores each sampled image for visible sunset-glow characteristics with a local vision-language model, and reports the average and maximum scores.

The score is a model-generated confidence index, not a statistically calibrated probability. SunsetScore evaluates visible appearance only: it does not use EXIF time or location, so a visually similar sunrise may also receive a high score.

## Features

- Runs locally after the initial model download, without an API key or cloud service
- Automatically uses a compatible GPU, with CPU override and automatic fallback
- Samples deterministically by naturally sorted relative path and filename
- Scans one directory or an entire directory tree with `-r` / `--recursive`
- Optionally analyzes every valid descendant directory independently and writes a Markdown report
- Reads a strict per-directory TOML configuration file
- Prints progress, per-image scores, reasons, and timing information
- Keeps logs on standard error and aggregate results on standard output
- Provides human-readable and JSON CLI output
- Exposes a small Python API that returns the average and maximum scores
- Skips individual unreadable images while preserving the rest of the run

## Requirements

- Python 3.10 or newer
- Windows 10/11 x64
- macOS on Intel or Apple Silicon
- A mainstream Linux x64 distribution
- Approximately 1.6 GB for CPU-only use, or roughly 3.2 GB with managed CUDA files
- JPG, JPEG, or PNG input images

SunsetScore can use CUDA on supported NVIDIA GPUs under Windows, Metal on macOS, and Vulkan on supported Windows or Linux GPUs. It does not support 32-bit systems, Linux ARM, RAW, HEIC, or AVIF.

## Installation

### Install from GitHub with pipx

`pipx` is recommended because it creates an isolated environment and exposes the `sunsetscore` command globally:

```console
pipx install "git+https://github.com/hanwenphotograph/Sunset-Score.git"
```

### Install into the current Python environment

```console
python -m pip install "git+https://github.com/hanwenphotograph/Sunset-Score.git"
```

### Install from a local checkout

```console
git clone https://github.com/hanwenphotograph/Sunset-Score.git
cd Sunset-Score
python -m pip install .
```

Verify the command after installation:

```console
sunsetscore --version
sunsetscore --help
```

Running `sunsetscore` without an input directory prints help and does not load or download the model.

## Quick Start

Score the supported images directly inside a directory:

```console
sunsetscore /path/to/photos
```

Recursively scan all subdirectories:

```console
sunsetscore -r /path/to/photos
```

Analyze each valid descendant directory independently and generate a report:

```console
sunsetscore -r --independently /path/to/photos
```

The shorter `-ind` alias is also available:

```console
sunsetscore -r -ind /path/to/photos
```

Override the sampling interval and emit a machine-readable result:

```console
sunsetscore /path/to/photos --interval 5 --json
```

Force CPU inference even when a compatible GPU is available:

```console
sunsetscore /path/to/photos --cpu-infer
```

Human-readable output:

```text
平均分: 68.40
最高分: 93
```

JSON output:

```json
{"average_score":68.4,"max_score":93}
```

Runtime logs are always written to standard error. The final text or JSON result is written to standard output, so external callers can capture it without parsing logs.

## Sampling Rules

SunsetScore sorts supported images by case-insensitive natural order. For example, `photo2.jpg` comes before `photo10.jpg`.

With the default interval of `10`, it samples positions `1, 11, 21, 31, ...`. A directory containing fewer than ten supported images still produces one sample. Recursive mode combines all discovered images into one globally sorted sequence before sampling.

Image symlinks, directory symlinks, and Windows reparse directories are ignored. Unsupported file formats are not included in the sequence.

## Independent Directory Analysis

`--independently` / `-ind` is valid only together with `-r` / `--recursive`. In this mode, SunsetScore recursively finds every descendant directory that directly contains at least one supported image and analyzes each directory as a separate sequence.

- Images directly inside the input root are excluded
- Each descendant directory processes only its own direct images
- Empty directories and directories containing only unsupported files are ignored
- Each directory reads its own `.sunsetscore.toml`
- A CLI `--interval` value overrides every local directory configuration
- One failed directory is recorded without discarding successful directory results

At the end of the run, the CLI prints every directory conclusion and writes a report under the input root:

```text
sunsetscore-analysis-YYYYMMDD-HHMMSS.md
```

The report contains model, inference backend and device metadata, image and sample counts, average and maximum scores, status, and failure details. Existing reports are never overwritten. If any directory fails, the report is still generated and the process exits with a non-zero status to indicate a partial result. With `--json`, standard output contains the complete directory result array and report path.

## Local Configuration

Create `.sunsetscore.toml` in the root of the input directory:

```toml
[sampling]
interval = 10
```

Configuration is validated strictly. Unknown keys, invalid types, and intervals below `1` stop the run with an error. Precedence from lowest to highest is: built-in default, local configuration, and the `--interval` CLI option.

## Model and Managed Runtime

The first scoring run automatically detects acceleration support, then downloads and verifies these pinned components:

- `llama.cpp b10040` runtime for the selected backend: approximately 11-640 MB of downloads
- `Qwen3-VL-2B-Instruct Q4_K_M` language model: approximately 1.11 GB
- `Qwen3-VL-2B-Instruct Q8_0` vision projector: approximately 445 MB

Backend priority and availability are:

1. CUDA 12.4 on Windows x64 when a compatible NVIDIA driver is detected
2. Metal on macOS
3. Vulkan on Windows or Linux when a Vulkan loader is available
4. CPU on every supported platform

Each GPU runtime is verified by listing its compute devices before it is selected. Installation or device-verification failure advances to the next candidate backend. If real GPU inference later fails, SunsetScore logs the reason and switches directly to CPU. `--cpu-infer` skips GPU detection and forces CPU execution. Models are shared between backends, while each managed runtime is cached separately.

Downloads provide progress logs, temporary files, HTTP resume support, SHA-256 verification, atomic installation, and one automatic retry. Subsequent runs can operate offline, although cached model files are still checked for integrity.

Managed files are stored in the platform-standard SunsetScore user data directory. Set `SUNSETSCORE_HOME` to place them somewhere else, including next to a portable installation:

```powershell
$env:SUNSETSCORE_HOME = "D:\Apps\SunsetScoreData"
sunsetscore D:\Photos
```

```bash
export SUNSETSCORE_HOME="$HOME/apps/sunsetscore-data"
sunsetscore ~/Pictures
```

Model weights come from the [official Qwen GGUF repository](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF). The inference runtime comes from [llama.cpp](https://github.com/ggml-org/llama.cpp).

## Score Interpretation

The fixed prompt gives the model these intended bands:

- `0-10`: no visible sky or no sunset-related evidence
- `11-20`: blue, gray, or black sky with no meaningful warm glow
- `21-49`: limited warm color that may come from ordinary lighting or a filter
- `50-74`: clearly visible warm sunset glow
- `75-94`: strong sunset colors or clouds illuminated by sunset glow
- `95-100`: large, intense, and unambiguous sunset glow

These bands describe the requested rubric, but a small generative vision-language model may not obey every numeric boundary consistently. Treat the scores as a coarse ranking signal and validate thresholds against your own photos before using them for automated decisions. The maximum score is generally more useful for answering whether a long sequence contains any sunset-glow frames, while the average can be diluted by many ordinary frames.

## Performance

On the development machine (`Ryzen 7 9700X` and `RTX 5070 Ti 16 GB`), the same image took 11.92 seconds with forced CPU inference and 1.82-1.96 seconds with warmed-up CUDA inference, a speedup of roughly 6x. The first CUDA inference after installation took 38.69 seconds because the driver compiled and cached kernels; later processes reused that cache. Timing depends on the selected backend and is reported in the per-image logs.

An approximate runtime is:

```text
runtime ≈ ceil(number of images / sampling interval) × time per inference
```

For example, a directory with about 1,800 images and the default interval of `10` produces about 180 inferences and took roughly 36-39 minutes on the development machine with CPU inference. The first run also downloads about 1.55 GB of model data plus the selected runtime.

## Python API

Python callers can obtain the aggregate conclusion directly:

```python
from sunsetscore import score_directories_independently, score_directory

result = score_directory("D:/Photos", recursive=True, interval=10)
print(result.average_score)
print(result.max_score)

batch = score_directories_independently("D:/Photo-Sessions", interval=10)
print(batch.report_path)
print(batch.inference_backend, batch.inference_device)
for directory in batch.directories:
    print(directory.directory, directory.average_score, directory.max_score)

cpu_result = score_directory("D:/Photos", cpu_infer=True)
```

`ScoreResult` intentionally exposes only `average_score` and `max_score`. Per-image scores, model reasons, success counts, and failure counts are written to runtime logs.

Unreadable or corrupt sampled images are logged and skipped without selecting a replacement. The run succeeds if at least one sample is scored. An empty input or a run in which every sample fails returns a non-zero exit code and does not emit fabricated scores.

## Development

```console
python -m pip install -e ".[test]"
python -m pytest
```

The automated test suite uses local substitutes and does not download the large model. The real model and runtime are installed only when an actual scoring run begins.
