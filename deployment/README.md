# 部署说明

状态：active。此目录保存发行包使用的推理脚本、客户端和配置。获取模型见[项目首页](../README.md)。下面命令在**发行ZIP解压根目录**运行；源码目录不包含模型和运行时。

## Windows GPU

解压GPU包后目录包含 `gguf/`、`runtimes/vulkan/`、`loader/`、`complete.py`。Python3.10+用于控制器/客户端，GGUF推理无需PyTorch。

AMD/Intel核显直接运行 `loader/start.cmd`。NVIDIA先运行 `powershell -ExecutionPolicy Bypass -File setup-runtime.ps1 -Backend cuda`，下载带SHA256校验的官方llama.cpp b11669运行时，然后打开加载器并扫描目录，选择CUDA0。

也可以直接运行 `start-gpu.ps1 -Backend vulkan` 或 `-Backend cuda`；命令行启动器独立于加载器，不要同时抢占18031端口。多GPU选择对应编号。驱动须支持Vulkan/CUDA12.4。

## Linux GPU

将GPU主包与Linux补充包解压到同一目录，保留 `gguf/` 和 `runtimes/linux-vulkan/llama-b11669/`。先执行 `bash setup-linux.sh` 解压已校验运行时，再执行 `bash loader/start.sh`，扫描根目录后选择Vulkan0；或者 `bash start-gpu.sh` 前台运行。Linux运行时必须有执行权限，必要时执行 `chmod +x runtimes/linux-vulkan/llama-b11669/llama-server`。

## Intel NPU（预览）

单独解压NPU包，先 `bash setup-npu.sh`，再 `bash loader/start.sh`。安装器建立 `.venv-npu`，固定OpenVINO/GenAI2026.4.1。Linux设备须具备Intel NPU驱动和 `/dev/accel/accel0` 读写权限，按Intel官方说明配置；加载器不安装系统驱动或修改权限。

Windows入口为 `setup-npu.ps1` 和加载器，需兼容NPU驱动；此平台未实机验收。已测155U/Linux，不将结果外推为155H或其他代际。NPU模型为OpenVINO INT4，不能直接用GGUF加载。首次编译可能较慢，缓存位于 `loader/npu-cache/`；试用时明确选择NPU。

## 原始v1（NVIDIA，独立推理版）

克隆仓库，将adapter发行包解压到仓库根目录，得到 `v1/adapter/`。推荐Linux/WSL和Python3.11；已有3090 24GB实测可用。

```bash
python3.11 -m venv .venv-v1
.venv-v1/bin/python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.venv-v1/bin/python -m pip install -r deployment/requirements-v1.txt
.venv-v1/bin/python deployment/download-v1-base.py
python3 loader/app.py
```

下载器从官方固定revision获取基座到 `v1/models/Qwen2.5-Coder-3B`，需要额外磁盘与网络。选择“v1 原始”，Python指向`.venv-v1/bin/python`，设备0。独立HTTP实现保留NF4双重量化、BF16与贪心FIM推理设置，不导入训练代码。仅含加载和推理。

## 客户端 / VS Code

服务启动后执行 `python complete.py --input examples.jsonl`。输入JSONL字段为library、prefix、suffix、mode（api/code）。输出syntax_ok仅表示语法，geometry_verified=false表示未核验几何。客户端不会执行用户代码。

将[continue.yaml](continue.yaml)模型条目合入Continue配置，保持autocomplete角色和FIM模板。端点18031；上下文预算1250tokens，API最多12/整句128tokens。服务提供 `/health`、`/tokenize`、`/completion`，不是聊天模型。

## 远端访问 / 故障

在服务器启动 `python3 loader/app.py --no-browser`，客户端用 `ssh -N -L 18030:127.0.0.1:18030 -L 18031:127.0.0.1:18031 USER@HOST` 转发。用户名和主机由你填写。不要直接把无鉴权推理端点暴露到公网。

端口被占用时先停止你已有的服务；加载器不会结束外部进程。加载失败展开日志，核对模型格式、运行时路径、环境Python和设备编号。停止模型再修改配置。下载损坏时按SHA256SUMS核验并重新下载；不覆盖唯一原文件。
