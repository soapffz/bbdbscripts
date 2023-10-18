"""
文件名: bbdb_clean.py
作者: soapffz
创建日期: 2023年10月1日
最后修改日期: 2023年10月15日

1. 除了github_project_monitor和github_user_organization_monitor表，删除其他所有表中business_id为空，或者没有business_id字段的行

2. 在business、root_domain、sub_domain、wechat_public_account、mini_program、app、mail、software_copyright表中使用name作为唯一值，在site表中使用url作为唯一值，在ip表中，使用address和port联合作为唯一值，github_project_monitor、github_user_organization_monitor、data_packet、blacklist表没有唯一值，使用对应的关系使得有唯一值设定的保持唯一

3. 所有有notes字段表，有notes字段但是为空的，设为"init by soapffz"

4. 所有create_time和update_time为空的字段，设置为2023年10月1日零点

5. 所有为列表的字段，列表中每一层也应当是唯一的

6. 脚本开始时一次性读取所有表到内存中，在内存中完成所有操作后批量操作数据库，应同时兼容内存和处理速度
"""
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId

# 连接MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["bbdb"]

# 定义需要处理的集合和它们的唯一字段
collections_unique_fields = {
    "business": "name",
    "root_domain": "name",
    "sub_domain": "name",
    "wechat_public_account": "name",
    "mini_program": "name",
    "app": "name",
    "mail": "name",
    "software_copyright": "name",
    "site": "url",
    "ip_address": ["address", "port"],
}

# 定义需要处理的集合和它们的notes字段
collections_notes_fields = [
    "business",
    "root_domain",
    "sub_domain",
    "wechat_public_account",
    "mini_program",
    "app",
    "mail",
    "software_copyright",
    "site",
    "ip_address",
    "github_project_monitor",
    "github_user_organization_monitor",
    "data_packet",
    "blacklist",
]

# 定义需要处理的集合和它们的create_time和update_time字段
collections_time_fields = [
    "business",
    "root_domain",
    "sub_domain",
    "wechat_public_account",
    "mini_program",
    "app",
    "mail",
    "software_copyright",
    "site",
    "ip_address",
    "github_project_monitor",
    "github_user_organization_monitor",
    "data_packet",
    "blacklist",
]

# 定义所有需要处理的集合
all_collections = (
    set(collections_unique_fields.keys())
    | set(collections_notes_fields)
    | set(collections_time_fields)
)

# 读取所有数据到内存
data = {}
for collection_name in all_collections:
    data[collection_name] = list(db[collection_name].find())

# 处理数据
for collection_name in all_collections:
    unique_values = set()  # 初始化unique_values
    for item in data[collection_name]:
        # 删除business_id为空或者没有business_id字段的行
        if "business_id" not in item or not item["business_id"]:
            data[collection_name].remove(item)
        else:
            # 保持唯一值
            if collection_name in collections_unique_fields:
                unique_field = collections_unique_fields[collection_name]
                if isinstance(unique_field, list):
                    unique_value = tuple(item[field] for field in unique_field)
                else:
                    unique_value = item[unique_field]
                if unique_value in unique_values:
                    data[collection_name].remove(item)
                else:
                    unique_values.add(unique_value)

            # 如果字段是列表，确保列表中的每个元素都是唯一的
            for field, value in item.items():
                if isinstance(value, list):
                    item[field] = list(set(value))

for collection_name in collections_notes_fields:
    for item in data[collection_name]:
        # 如果notes字段为空，设为"init by soapffz"
        if "notes" not in item or not item["notes"]:
            item["notes"] = "init by soapffz"

for collection_name in collections_time_fields:
    for item in data[collection_name]:
        # 如果create_time和update_time为空，设置为2023年10月1日零点
        if "create_time" not in item or not item["create_time"]:
            item["create_time"] = datetime(2023, 10, 1)
        if "update_time" not in item or not item["update_time"]:
            item["update_time"] = datetime(2023, 10, 1)

# 批量更新数据库
for collection_name in collections_unique_fields.keys():
    for item in data[collection_name]:
        db[collection_name].replace_one({"_id": ObjectId(item["_id"])}, item)
