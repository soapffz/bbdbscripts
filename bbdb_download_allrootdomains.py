from pymongo import MongoClient
import os
import yaml

# 读取配置文件
with open("config_product.yaml", "r") as f:
    config = yaml.safe_load(f)

# 连接MongoDB
mongodb_uri = config["DEFAULT"].get("BBDB_MONGODB_URI")
try:
    client = MongoClient(mongodb_uri)
    db = client["bbdb"]
except Exception as e:
    print(f"连接MongoDB时发生错误：{e}")
    exit(1)

# 从root_domain集合中提取所有的域名
domains = db["root_domain"].find({}, {"name": 1, "_id": 0})

# 去重并排序
unique_domains = sorted({domain["name"] for domain in domains})

# 检查文件是否存在，如果存在则删除
if os.path.exists("all_bbdb_rootdomains.txt"):
    os.remove("all_bbdb_rootdomains.txt")

# 输出到文件
with open("all_bbdb_rootdomains.txt", "w") as f:
    for domain in unique_domains:
        f.write(domain + "\n")
