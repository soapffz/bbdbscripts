import os
from pymongo import MongoClient

# 从环境变量中读取MongoDB URI
mongodb_uri = os.getenv("BBDB_MONGOURI")

# 连接MongoDB
try:
    client = MongoClient(mongodb_uri)
    db = client["bbdb"]
except Exception as e:
    print(f"连接MongoDB时发生错误：{e}")
    exit(1)

# 从root_domain集合中提取所有的域名
domains = [domain["name"] for domain in db["root_domain"].find({}, {"name": 1, "_id": 0})]

# 去重并排序
unique_domains = sorted(set(domains))

# 检查文件是否存在，如果存在则删除
output_file = "all_bbdb_rootdomains.txt"
if os.path.exists(output_file):
    os.remove(output_file)

# 输出到文件
with open(output_file, "w") as f:
    f.write("\n".join(unique_domains))
