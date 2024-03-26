# -*- coding: utf-8 -*-

"""
new Env('依赖安装');
8 8 2 10 * https://raw.githubusercontent.com/soapffz/bbdbscripts/arl_bbdb_deps.py
"""

import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

# 系统级别的库白名单
WHITELISTED_LIBS = {'os', 're', 'subprocess', 'datetime', 'timedelta', 'timezone', 'sys', 'math', 'collections', 'functools', 'itertools', 'json'}

def get_deps_from_file(file_path):
    """从 Python 文件中提取依赖项"""
    deps = set()
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('import '):
                deps.update(re.findall(r'import\s+(\w+)', line))
            elif line.startswith('from '):
                parts = re.findall(r'from\s+(\w+)\s+import', line)
                if parts:
                    module = parts[0]
                    deps.add(module)
    return deps


def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")


def install_deps(deps):
    """安装依赖项"""
    for dep in deps:
        log_message(f"Installing {dep}")
        try:
            subprocess.check_call(['pip', 'install', dep])
            log_message(f"{dep} installed successfully", is_positive=True)
        except subprocess.CalledProcessError:
            log_message(f"Failed to install {dep}", is_positive=False)

if __name__ == '__main__':
    all_deps = set()
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                all_deps.update(get_deps_from_file(file_path))
    install_deps(all_deps - WHITELISTED_LIBS)
