# CAD Completion 3B — CAD代码补全与本地部署

**Built with Qwen** · 专用于 **CadQuery 2.7.0 / build123d 0.13.0** 的 API、拉伸、切除、圆角等短CAD操作和简短中文注释后的补全。基础模型为 Qwen2.5-Coder-3B，正式微调版本为 v1。

本仓库公开部署加载器、推理代码和使用说明；**不公开训练代码、训练数据或内部实验记录**。模型权重在 Releases，源码仓库不存放多GB模型。

## 下载与选择

[打开 v1.0.0 Releases](https://github.com/Austrust/cad-completion-3b/releases/tag/v1.0.0)

| 设备 / 需求 | 下载附件 | 状态 |
|---|---|---|
| Windows AMD / Intel核显 / NVIDIA | `CAD-completion-3B-v1-Q4-Windows-GPU-public.zip` | GGUF Q4_K_M；内含加载器和Vulkan；NVIDIA首次安装CUDA运行时 |
| Linux Intel / AMD Vulkan | 上述GPU包 + `CAD-completion-3B-v1-Linux-Vulkan-public.zip` | 同一GGUF；补充Linux运行时 |
| Intel Core Ultra NPU | `CAD-completion-3B-v1-Intel-NPU-preview-public.zip` | 独立OpenVINO INT4；155U/Linux实测，仍是预览 |
| NVIDIA 原始v1 NF4/BF16 | `CAD-completion-3B-v1-adapter-public.zip` + 官方固定基座 | 独立推理路径，无训练代码；见部署说明 |
| 已经有模型和运行时 | `CAD-model-loader-public.zip` | 仅加载器，无权重 |

每个ZIP的SHA-256在 `SHA256SUMS.txt`；解压后的 `manifest.json` 记录逐文件摘要。模型许可限定非商业研究与评估，详见下方许可。

## Windows快速开始

1. 安装 Python 3.10+，确保 `python` 命令可用；准备对应显卡驱动。
2. 解压GPU包。AMD/Intel核显直接双击 `loader/start.cmd`。
3. NVIDIA先在解压目录执行 `powershell -ExecutionPolicy Bypass -File .\setup-runtime.ps1 -Backend cuda`，再启动加载器。在“发现已有模型”中扫描解压目录，选择 `CUDA0` 配置。
4. 浏览器打开 **http://127.0.0.1:18030**，选模型并点“启动服务”。
5. “停止服务”卸载模型；“退出加载器”同时退出控制界面服务。关闭网页会保留推理服务。

## Linux / Intel NPU / 原始v1

详细环境、解压目录、启动命令和常见问题见 [部署说明](deployment/README.md)。Linux GPU解压两个包到同一目录后先执行 `bash setup-linux.sh`，再执行 `bash loader/start.sh`；NPU先执行 `bash setup-npu.sh` 再启动加载器。Windows NPU入口随附，尚未实机验收。

## VS Code补全

安装 Continue，将 [continue.yaml](deployment/continue.yaml) 的模型配置合入你现有的配置。选择 autocomplete 角色，接口为 `http://127.0.0.1:18031`，保持原始FIM模板，**不要使用聊天模板**。加载器也可以显示配置。切换模型不用修改VS Code端点。

```python
# Library: build123d 0.13.0
from build123d import *
height = 8
sketch = Rectangle(30, 20)
# 拉伸草图
result = # 光标放在等号后，等待补全
```

应保留import、对象创建、尺寸与注释。模型根据光标前后上下文补全，不负责完整零件设计。示例中的光标占位需要删除。后端/客户端已实测，Continue扩展UI尚未端到端验收。

## 实测和限制

GPU量化在已打开的618例合成上下文回归中，NVIDIA/AMD/Intel核显的短中文整句均为95.4%；NPU为93.5%，所以继续标为预览。**这不是任意真实项目95%正确的保证。** 已知新界面探针中CadQuery可能把拉伸高度误写为 `until=height`。补全代码需要检查并执行几何验证。

详细逐任务表、设备、计分口径和加载器实测范围见 [验证说明](docs/VALIDATION.md)。本仓库不发布内部评测集。

## 源码导航

- [loader/](loader/README.md)：模型发现、启动/停止、日志和补全试用的网页控制器。
- [deployment/](deployment/README.md)：现有llama.cpp/OpenVINO启动脚本、原始v1推理准备、JSONL客户端和Continue配置。
- [docs/](docs/README.md)：实测范围和界面预览。
- [THIRD-PARTY-LICENSES/](THIRD-PARTY-LICENSES/README.md)：第三方运行时许可。

## 许可

模型是Qwen2.5-Coder-3B的修改衍生物，保留 [Qwen Research License](MODEL-LICENSE.txt) 和 [NOTICE](NOTICE.txt)：仅限非商业研究与评估，商业使用需向Alibaba Cloud另获许可。基座固定revision为 `ac059254f4aa58c1078b15635a33f6de9b96f0fa`。

项目部署源码目前仅公开查看，未另行授予MIT等开源许可证，见 [COPYRIGHT](COPYRIGHT.txt)。llama.cpp及其他第三方组件遵守各自许可；公开发布不改变模型和第三方条款。
