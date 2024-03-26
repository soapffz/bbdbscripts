"""
new Env('测试-导出根域名');
50 23 * * * https://raw.githubusercontent.com/soapffz/bbdbscripts/main/debug_bbdb_download_allrootdomains.py
"""

import os
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "\[ + \]" if is_positive else "\[ - \]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

# 从环境变量中读取MongoDB URI
mongodb_uri = os.getenv("BBDB_MONGOURI")

# 连接MongoDB
try:
    client = MongoClient(mongodb_uri)
    db = client["bbdb"]
    log_message("成功连接到MongoDB")
except Exception as e:
    log_message(f"连接MongoDB时发生错误：{e}", is_positive=False)
    exit(1)

# 从root_domain集合中提取所有的域名
domains = [domain["name"] for domain in db["root_domain"].find({}, {"name": 1, "_id": 0})]
log_message(f"从MongoDB中获取到{len(domains)}个域名")

# 去重并排序
unique_domains = sorted(set(domains))
log_message(f"去重后剩余{len(unique_domains)}个域名")

# 检查文件是否存在，如果存在则删除
output_file = "all_bbdb_rootdomains.txt"
if os.path.exists(output_file):
    os.remove(output_file)
    log_message(f"删除已存在的{output_file}文件")

# 输出到文件
with open(output_file, "w") as f:
    f.write("\n".join(unique_domains))
log_message(f"成功将{len(unique_domains)}个域名写入{output_file}")
