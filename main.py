import sys
import os

# 将项目根目录添加到sys.path，以便main.py可以找到interfaces等模块
sys.path.append(os.path.dirname(__file__))

from interfaces.cli import run_cli

def main():
    """
    项目主入口。
    直接启动命令行界面。
    """
    run_cli()

if __name__ == '__main__':
    main() 