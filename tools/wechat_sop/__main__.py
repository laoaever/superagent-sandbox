"""`python3 -m wechat_sop` 的入口模块。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
