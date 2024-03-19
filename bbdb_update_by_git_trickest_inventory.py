"""
文件名: bbdb_update_by_git_trickest_inventory.py
作者: soapffz
创建日期: 2024年3月19日
最后修改日期: 2024年3月19日

1.在脚本运行之前先在/ql目录git clone https://github.com/trickest/inventory.git git_trickest_inventory
2.将所有文件夹中的hostnames.txt文件读取，与已有子域名和黑名单库进行比较，插入新的域名
"""
import os
from datetime import datetime
from pymongo import MongoClient

# 打印信息的函数
def log_message(message, is_positive=True):
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

# 检查git文件夹
git_folder = "/ql/git_trickest_inventory"
if not os.path.isdir(git_folder) or not os.listdir(git_folder):
    log_message("git文件夹不存在或为空，请先运行git clone再运行此脚本", False)
    exit()
log_message("git文件夹正常")

# 连接到MongoDB
BBDB_MONGOURI = os.getenv("BBDB_MONGOURI")
client = MongoClient(BBDB_MONGOURI)
db = client.bbdb
log_message("数据库连接成功，准备读取...")

# 读取数据库表
businesses = list(db.business.find())
root_domains = list(db.root_domain.find())
sub_domains = list(db.sub_domain.find())
blacklist = set(item['name'] for item in db.blacklist.find({"type": "sub_domain"}))
log_message("数据库读取完成")

# 读取所有hostnames.txt文件的内容并合并
all_hostnames = set()
cmd_find_files = f"find {git_folder} -type f -name 'hostnames.txt'"
hostnames_files = os.popen(cmd_find_files).read().strip().split('\n')
for file_path in hostnames_files:
    with open(file_path, 'r') as file:
        all_hostnames.update(file.read().strip().split('\n'))
log_message("所有hostnames.txt内容已合并，开始查找，只输出可能的新域名数量，时间耗时较长，请耐心等待...")

# 更新子域名
for root_domain in root_domains:
    domain_name = root_domain['name']
    found_subdomains = {hostname for hostname in all_hostnames if hostname.endswith(f".{domain_name}")}
    if len(found_subdomains) == 0:
        continue
    
    log_message(f"{domain_name} 在git库中查找到 {len(found_subdomains)} 个可能的新域名")
    
    # 过滤已存在的子域名和黑名单中的子域名
    existing_subdomains = {sub['name'] for sub in sub_domains if sub['root_domain_id'] == str(root_domain['_id'])}
    new_subdomains = found_subdomains - existing_subdomains - blacklist
    
    # 构建新的子域名文档并插入
    new_subdomain_docs = [{
        "name": subdomain,
        "icpregnum": "",
        "company": "",
        "company_type": "",
        "root_domain_id": str(root_domain['_id']),
        "business_id": str(root_domain['business_id']),
        "notes": "set by script with ql",
        "create_time": datetime.now(),
        "update_time": datetime.now()
    } for subdomain in new_subdomains]
    
    if new_subdomain_docs:
        # 实际插入数据库操作
        # db.sub_domain.insert_many(new_subdomain_docs)
        log_message(f"根域名 {domain_name} 插入了 {len(new_subdomain_docs)} 个新的子域名。")

log_message("更新完成。")
