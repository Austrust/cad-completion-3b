param([string]$Python='python')
$ErrorActionPreference='Stop'
$envDir=Join-Path $PSScriptRoot '.venv-npu'
if(Test-Path -LiteralPath $envDir){throw 'Environment already exists; inspect it before changing dependencies'}
& $Python -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"; assert sys.maxsize > 2**32, "64-bit Python required"'
if($LASTEXITCODE -ne 0){throw 'Python version check failed'}
& $Python -m venv $envDir
if($LASTEXITCODE -ne 0){throw 'Cannot create local runtime environment'}
$pythonExe=Join-Path $envDir 'Scripts/python.exe'
& $pythonExe -m pip install -r (Join-Path $PSScriptRoot 'requirements-npu.txt')
if($LASTEXITCODE -ne 0){throw 'Runtime install failed'}
& $pythonExe (Join-Path $PSScriptRoot 'openvino-server.py') --device NPU --check-device
if($LASTEXITCODE -ne 0){throw 'NPU unavailable: check the Intel NPU driver and hardware. No CPU fallback was started.'}
