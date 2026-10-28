# 模型加载器

状态：active。输入已有GGUF、OpenVINO或v1基座+adapter，输出统一的本机补全端点。复用llama.cpp / OpenVINO / Transformers+PEFT。

Windows双击 `start.cmd`；Linux执行 `bash start.sh`。依赖Python3.10+，控制器只用标准库；推理依赖见[部署说明](../deployment/README.md)。

界面18030、推理18031，仅监听127.0.0.1。选择模型→启动服务→补全测试；停止服务释放模型资源。更换模型前先停止，关闭网页不等于停止服务。

模型配置可保存GGUF文件和llama-server路径、OpenVINO目录和对应环境Python、v1目录和兼容adapter路径。设备为 `Vulkan0` / `CUDA0` / `CPU`，OpenVINO为 `NPU` / `GPU` / `CPU`，原始v1为CUDA编号 `0`。没有目标设备会报错，不自动回退。

在“发现已有模型”填写解压目录扫描；NVIDIA运行时安装后重新扫描。自定义版本可新增配置，但不继承v1质量成绩。状态、模型路径与日志仅保存在本机 `state/`。

控制器：`python app.py --root <解压根目录> --port 18030 --service-port 18031`。已有配置保留，改变root后需扫描。原始v1只需 `models/Qwen2.5-Coder-3B/` 与 `adapter/`，不需要训练源码。

“显示VS Code配置”提供Continue autocomplete/FIM示例。补全测试不执行CAD代码、不验证几何。详见[验证范围](../docs/VALIDATION.md)。

运维测试：项目根目录运行 `python -m unittest discover -s loader -p test_loader.py -v`。测试不下载模型。
