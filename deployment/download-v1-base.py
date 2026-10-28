"""Download only the pinned official base for local inference."""
from pathlib import Path
from huggingface_hub import snapshot_download
root=Path(__file__).resolve().parents[1]
snapshot_download(repo_id="Qwen/Qwen2.5-Coder-3B",revision="ac059254f4aa58c1078b15635a33f6de9b96f0fa",local_dir=root/"v1/models/Qwen2.5-Coder-3B",allow_patterns=["*.json","*.safetensors","*.txt","*.tiktoken","LICENSE","README.md"])
