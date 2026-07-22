# SunsetScore

[English](README.md) | [简体中文](README_CN.md)

SunsetScore is a cross-platform Python CLI that scores one photo or samples photos from a directory with a local vision-language model. Directory runs report whether qualifying sunset glow was detected and where it occurs. A sunset without visibly colored clouds does not qualify.

The score is a coarse index deterministically mapped from the model's mutually exclusive visual category, not a statistically calibrated probability. SunsetScore evaluates visible appearance only: it does not use EXIF time or location, so visually similar sunrise-lit clouds may also receive a high score.

## Scoring Examples

These crops come from one scored timelapse sequence and focus on the cloud area. The lower-left label is the score stored by SunsetScore. This run produced no score-5 sample, so scores 1, 3, and 4 represent its typical low, medium, and high cases.

| Low | Medium | High |
|:---:|:---:|:---:|
| ![Low score example: ordinary white and gray clouds without sunset coloring, scored 1 out of 5](docs/images/score-examples/low-score-1.jpg) | ![Medium score example: clearly but softly colored clouds, scored 3 out of 5](docs/images/score-examples/medium-score-3.jpg) | ![High score example: vivid coloring across a broad cloud area, scored 4 out of 5](docs/images/score-examples/high-score-4.jpg) |
| **1 / 5**<br>Ordinary white and gray clouds without sunset coloring. | **3 / 5**<br>Clear but soft, moderately intense cloud coloring. | **4 / 5**<br>Vivid coloring across a broad area of the clouds. |

## Features

- Runs locally after the initial model download, without an API key or cloud service
- Automatically uses a compatible GPU, with CPU override and automatic fallback
- Reuses one local inference service and runs up to two requests concurrently without duplicating model processes
- Scores an individual JPG, JPEG, or PNG and returns the model's reason
- Samples deterministically by naturally sorted relative path and filename
- Scans one directory or an entire directory tree with `-r` / `--recursive`
- Optionally analyzes every valid descendant directory independently and writes a Markdown report
- Copies complete detected sunset ranges into a managed `SunsetResult` directory with `--autopack`
- Persists successful directory scores and reuses them on later runs
- Reads a strict per-directory TOML configuration file
- Prints progress, per-image scores, reasons, and timing information
- Keeps logs on standard error and final results on standard output
- Provides human-readable and JSON CLI output
- Exposes a small Python API for individual scores and directory conclusions
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

Running `sunsetscore` without an input path prints help and does not load or download the model.

## Quick Start

Score one photo and print its score and reason:

```console
sunsetscore /path/to/photo.jpg
```

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

Re-score a directory even when it already contains a score file:

```console
sunsetscore /path/to/photos --force
```

Copy every original photo inside detected sunset ranges into `SunsetResult`:

```console
sunsetscore /path/to/photos --autopack
sunsetscore -r -ind /path/to/photo-sessions --autopack
```

Force CPU inference even when a compatible GPU is available:

```console
sunsetscore /path/to/photos --cpu-infer
```

Cap shared GPU service slots, the scheduling memory budget, or both:

```console
sunsetscore /path/to/photos --gpu-workers 2
sunsetscore /path/to/photos --gpu-memory-limit 6
sunsetscore /path/to/photos --gpu-workers 2 --gpu-memory-limit 10
```

Single-photo text output:

```text
评分: 4 / 5
理由: 大范围云层呈现鲜艳霞光着色
```

Single-photo JSON output:

```json
{"score":4,"reason":"大范围云层呈现鲜艳霞光着色"}
```

Directory text output:

```text
平均分: 3.40
最高分: 5
检测到晚霞: 是
晚霞区间: photo101.jpg 至 photo131.jpg
```

Directory JSON output:

```json
{"average_score":3.4,"max_score":5,"has_sunset":true,"sunset_ranges":[{"start_photo":"photo101.jpg","end_photo":"photo131.jpg"}]}
```

Runtime logs are always written to standard error. The final text or JSON result is written to standard output, so external callers can capture it without parsing logs.

Single-photo runs always perform one inference and do not create or reuse a directory score file. They support `--cpu-infer`, `--gpu-workers`, `--gpu-memory-limit`, and `--json`. Directory-only options such as recursive scanning, sampling intervals, forced cache refresh, independent analysis, and automatic packing are rejected for a photo input.

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

At the end of a run that performs inference, the CLI prints every directory conclusion and writes a report under the input root:

```text
sunsetscore-analysis-YYYYMMDD-HHMMSS.md
```

The report contains model, inference backend, device, inference-slot and memory-limit metadata, image and sample counts, the Boolean detection, sunset ranges, average and maximum scores, status, and failure details. New reports never overwrite existing files. A run that uses only compatible cached scores reuses the newest existing report instead of creating a duplicate; it creates one only when no report exists. If any directory fails, a new inference report is still generated and the process exits with a non-zero status to indicate a partial result. With `--json`, standard output contains the complete directory result array and report path.

## Automatic Packing

`--autopack` creates `SunsetResult` under the input directory. For each detected range, SunsetScore copies every supported original photo from the start endpoint through the end endpoint in natural sequence order, not only the sampled endpoint photos.

For a direct directory, photos are written directly under `SunsetResult`. Recursive single-directory runs preserve source-relative paths. Independent-directory runs also preserve each source directory below `SunsetResult`, so identically named photos from different sessions remain separate.

`SunsetResult` is fully managed by SunsetScore. Each successful packing run builds a temporary directory first and then replaces the previous result, so stale photos are removed while a failed copy leaves the prior result intact. Do not keep manually managed files inside it. The directory is excluded from later recursive scans.

Compatible score files are reused automatically, so `--autopack` can package a previous inference result without loading the model again. Use `--force` together with `--autopack` when photos or scoring inputs changed. A cache-only independent run also reuses its newest Markdown report. The flag itself does not create JSON files in the input root; `--json` continues to write only to standard output.

## Score Files

After a directory is scored successfully, SunsetScore writes this JSON file inside that directory:

```text
.sunsetscore-score.json
```

A normal or recursive single-directory run writes the file in the input directory. Independent mode writes one file in every successfully scored descendant directory; failed directories do not receive a score file.

On a later run with the same recursive scope, SunsetScore reads the file and skips model initialization and inference. Cache files include the SunsetScore application version, ordered sample positions, relative photo paths, scores, and reasons. A cache from a different application version is ignored and atomically replaced after a successful run. Use `-f` / `--force` to refresh a same-version cache. Changes to photos, sampling configuration, the CLI interval, or the model do not otherwise invalidate a same-version score, so use `--force` when any of those changes should affect the result. Invalid or unsupported score files are also ignored and replaced after a successful run.

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

Each GPU runtime is verified by listing its compute devices before it is selected. Installation or device-verification failure advances to the next candidate backend. SunsetScore starts one loopback-only `llama-server`, loads the model once, and sends concurrent image requests to shared server slots. If real GPU inference later fails, the service is stopped, SunsetScore logs the reason, and a CPU service is started instead. `--cpu-infer` skips GPU detection and forces CPU execution. Models are shared between backends, while each managed runtime is cached separately.

For batches containing multiple samples, automatic scheduling reserves 6 GiB of currently free device memory for multimodal projection, budgets 4 GiB per additional request slot, and uses at most two shared slots. Unknown device memory selects one slot. `--gpu-workers` accepts `1` or `2` and sets a slot limit. `--gpu-memory-limit` sets a scheduling budget in GiB and has a minimum value of `3`; it remains an approximation rather than a driver-enforced hard VRAM cap. If free device memory is unknown or below the 6 GiB safety margin, the visual projector runs on CPU while language-model layers may still use the GPU. Input images and dynamic vision tokens are both capped at `1024`. GPU limit options cannot be used with `--cpu-infer`.

Downloads provide progress logs, temporary files, HTTP resume support, SHA-256 verification, atomic installation, and one automatic retry. Subsequent runs can operate offline, although cached model files are still checked for integrity.

When SunsetScore receives a catchable termination signal, it stops the inference service, performs an orderly shutdown, and removes incomplete download, runtime-installation, normalized-image, lock, and report temporary data. Verified models and installed runtimes remain cached. An operating-system hard kill cannot run in-process cleanup.

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

The fixed prompt asks the model for one mutually exclusive visual category, which the application maps to these representative scores:

- `0`: no visible sky or no evidence of sunset-lit clouds
- `1`: no recognizable natural clouds or no glow color on the clouds, including a clear-sky sunset, warm horizon, and ordinary white clouds
- `2`: weak, local, or ambiguous warm or purple coloration on the clouds
- `3`: clear cloud coloration that remains soft and local or covers only a small area
- `4`: visibly vivid or high-contrast cloud coloration, or colored clouds covering a broad area of the sky
- `5`: vivid, intense, richly layered colored clouds covering most of the visible sky

The discrete categories prevent a small generative vision-language model from returning a number that contradicts its own classification. Treat the scores as a coarse signal and validate the detection rule against your own photos before using it for automated decisions.

## Sunset Detection

A sampled photo is high-scoring at `3` or above. A high score requires recognizable cloud bodies visibly colored red, orange, pink, gold, or glow-lit purple; a clear-sky sunset showing only the sun, warm sky, or horizon cannot reach this threshold. For sequences with at least three sampled positions, SunsetScore reports `has_sunset = true` when any sliding window of three positions contains at least two high-scoring photos. This rejects an isolated high score without diluting a short sunset event with the average of a long sequence. For a sequence with fewer than three sampled positions, any high-scoring photo produces a positive result.

Only high-scoring photos that participate in a qualifying window are included in `sunset_ranges`. Adjacent qualifying sample positions form one inclusive range; a low-scoring or failed position splits the range. Each endpoint is a photo path relative to the input directory, which is a plain filename for non-recursive and independent-directory runs. Average and maximum scores remain available for compatibility and diagnostics but do not determine the Boolean result.

## Performance

The persistent service removes per-image model loading and shares model weights, the visual projector, and the CUDA context across all requests. A 16 GiB GPU normally selects two slots, while `--gpu-workers 1` provides the most conservative mode. Actual throughput depends on image complexity, backend, and whether the visual projector can remain on the GPU.

An approximate runtime is:

```text
samples ≈ ceil(number of images / sampling interval)
runtime ≈ ceil(samples / slots) × concurrent-batch time
```

For example, a directory with about 1,800 images and the default interval of `10` produces about 180 inferences and took roughly 36-39 minutes on the development machine with CPU inference. The first run also downloads about 1.55 GB of model data plus the selected runtime.

## Python API

Python callers can score one photo or obtain an aggregate directory conclusion directly:

```python
from sunsetscore import score_directories_independently, score_directory, score_image

photo = score_image("D:/Photos/sunset.jpg")
print(photo.score, photo.reason)

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

The two directory scoring functions reuse compatible score files by default and accept `force=True` to refresh them. `score_image` always performs inference and returns a `PhotoScore` containing `score` and `reason`. `ScoreResult` exposes `has_sunset`, `sunset_ranges`, `average_score`, and `max_score`. Ordered per-image scores and model reasons from directory runs are retained in the versioned score file and written to runtime logs.

Unreadable or corrupt sampled images are logged and skipped without selecting a replacement. The run succeeds if at least one sample is scored. An empty input or a run in which every sample fails returns a non-zero exit code and does not emit fabricated scores.

## Development

```console
python -m pip install -e ".[test]"
python -m pytest
```

The automated test suite uses local substitutes and does not download the large model. The real model and runtime are installed only when an actual scoring run begins.
