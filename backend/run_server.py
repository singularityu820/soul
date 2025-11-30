import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 加载环境变量
project_root = backend_dir.parent
load_dotenv(project_root / ".env")
load_dotenv(backend_dir / "baidu_api_config.env")

# 现在可以导入app模块
from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)