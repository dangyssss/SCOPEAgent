from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# 配置服务地址前缀和实际路径绑定（递归读取所有文件）
BASE_DIR = "mcp_service"
PORT = 8003

# 暴露整个目录作为静态文件访问（files/路径）
app.mount("/files", StaticFiles(directory=BASE_DIR), name="files")

@app.get("/list_files")
def list_all_screenshot_and_log_files():
    """
    遍历 testAgent1/2/3 中所有子文件夹，收集截图和 log 文件路径
    返回: { 逻辑路径: 完整URL }
    """
    allowed_exts = (".png", ".jpg", ".jpeg", ".log")
    target_roots = ["testAgent1", "testAgent2", "testAgent3"]
    file_urls = {}

    for root in target_roots:
        full_root_path = os.path.join(BASE_DIR, root)
        for dirpath, _, filenames in os.walk(full_root_path):
            for fname in filenames:
                if fname.lower().endswith(allowed_exts):
                    rel_path = os.path.relpath(os.path.join(dirpath, fname), BASE_DIR).replace("\\", "/")
                    file_url = f"http://localhost:{PORT}/files/{rel_path}"
                    file_urls[rel_path] = file_url

    return file_urls

