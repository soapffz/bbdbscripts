# -*- coding: utf-8 -*-

"""
new Env('依赖安装');
8 8 2 10 * https://raw.githubusercontent.com/YourRepo/main/arl_bbdb_deps.py
"""

import subprocess
import sys
import time
import pkg_resources

REQUIRED_PACKAGES = ["pymongo", "requests", "pyyaml", "datetime"]


def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


print("只有在第一次运行脚本提示缺少依赖时才运行此程序，如果没有问题请勿运行，以免弄出问题!!!")
time.sleep(2)
print("5s后开始安装依赖......")
time.sleep(5)

# 安装ARL和bbdb所需的依赖
for package in REQUIRED_PACKAGES:
    try:
        dist = pkg_resources.get_distribution(package)
        print("{} ({}) is installed".format(dist.key, dist.version))
    except pkg_resources.DistributionNotFound:
        print("{} is NOT installed".format(package))
        install(package)
