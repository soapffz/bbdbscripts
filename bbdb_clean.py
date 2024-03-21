"""
文件名: bbdb_clean.py
作者: soapffz
创建日期: 2023年10月1日
最后修改日期: 2024年3月21日

以下清洗步骤建议不要调换顺序

1.删除所有表中有business_id、root_domain_id、sub_domain_id任何一个字段，但是其中任何一个字段为空的文档。
2.将所有表中有business_id、root_domain_id、sub_domain_id字段，但是格式不是为string类型，而是ObjectId类型的地方转化为string类型。
3.所有表中notes字段为空的文档，都将其设置为"set by soapffz"。
4.每个表都必须有create_time和update_time字段，如果没有则创建，如果为空也将两个字段都设置为当前时间的北京时间。
5.所有表中的name字段都应保持唯一，删除所有name字段重复的较老文档。
6.使用business_id、root_domain_id、sub_domain_id去相应表中查找，但是没有查找到对应文档的文档，查找逻辑为business_id为business表中的_id，root_domain_id为root_domain表中的_id，sub_domain_id为sub_domain的_id。
7.删除所有root_domain和sub_domain表中name字段为ipv4地址的文档。(新增功能)
8.将所有表中包含{"$numberDouble":"NaN"}这种空内容的文档，替换为"set by soapffz by clean"。(新增功能)
"""

from pymongo import MongoClient, UpdateOne
import os
from datetime import datetime, timedelta
from bson.objectid import ObjectId

# 初始化MongoDB连接
mongodb_uri = os.getenv("BBDB_MONGOURI")
client = MongoClient(mongodb_uri)
db = client['bbdb']

def log(message, is_positive=True):
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')} {prefix} {message}")

def clean_empty_fields():
    # 实现需求1
    start_time = datetime.now()
    total_deleted = 0  # 初始化删除文档的总数

    collections_to_clean = db.list_collection_names()
    for collection_name in collections_to_clean:
        collection = db[collection_name]
        result = collection.delete_many({
            "$or": [
                {"$and": [{"business_id": {"$exists": True}}, {"business_id": {"$in": [None, ""]}}]},
                {"$and": [{"root_domain_id": {"$exists": True}}, {"root_domain_id": {"$in": [None, ""]}}]},
                {"$and": [{"sub_domain_id": {"$exists": True}}, {"sub_domain_id": {"$in": [None, ""]}}]}
            ]
        })
        total_deleted += result.deleted_count

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_deleted > 0:
        log(f"步骤1运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤1运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def convert_id_to_string():
    # 实现需求2
    start_time = datetime.now()
    total_converted = 0  # 初始化转换文档的总数

    collections_to_convert = db.list_collection_names()
    for collection_name in collections_to_convert:
        collection = db[collection_name]
        fields_to_convert = ["business_id", "root_domain_id", "sub_domain_id"]
        updates = []
        for document in collection.find({}):
            update_fields = {}
            for field in fields_to_convert:
                if field in document and isinstance(document[field], ObjectId):
                    update_fields[field] = str(document[field])
            if update_fields:
                updates.append(UpdateOne({"_id": document["_id"]}, {"$set": update_fields}))
        if updates:
            result = collection.bulk_write(updates)
            total_converted += len(updates)

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_converted > 0:
        log(f"步骤2运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_converted}")
    else:
        log(f"步骤2运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def set_default_notes():
    # 实现需求3
    start_time = datetime.now()
    total_updated = 0  # 初始化更新文档的总数

    collections_to_update = db.list_collection_names()
    for collection_name in collections_to_update:
        collection = db[collection_name]
        query = {"notes": {"$in": [None, "", []]}}  # 匹配空字符串、null或空数组
        update = {"$set": {"notes": "set by soapffz"}}
        result = collection.update_many(query, update)
        total_updated += result.modified_count

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_updated > 0:
        log(f"步骤3运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_updated}")
    else:
        log(f"步骤3运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def ensure_time_fields():
    # 实现需求4
    start_time = datetime.now()
    total_updated = 0  # 初始化更新文档的总数

    collections_to_update = db.list_collection_names()
    for collection_name in collections_to_update:
        collection = db[collection_name]
        updates = []
        # 获取当前北京时间
        now = datetime.utcnow() + timedelta(hours=8)
        documents = collection.find({})
        for document in documents:
            update_fields = {}
            # 如果create_time或update_time不存在或为空，则设置它们为当前北京时间
            if not document.get('create_time'):
                update_fields['create_time'] = now
            if not document.get('update_time'):
                update_fields['update_time'] = now
            # 如果需要更新字段，则添加到更新列表中
            if update_fields:
                updates.append(UpdateOne({'_id': document['_id']}, {'$set': update_fields}))
        # 执行批量更新
        if updates:
            result = collection.bulk_write(updates)
            total_updated += len(updates)

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_updated > 0:
        log(f"步骤4运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_updated}")
    else:
        log(f"步骤4运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def ensure_unique_name():
    # 实现需求5
    start_time = datetime.now()
    total_deleted = 0  # 初始化删除文档的总数

    collections_to_update = db.list_collection_names()
    for collection_name in collections_to_update:
        collection = db[collection_name]
        # 使用聚合管道查找重复的name值
        pipeline = [
            {"$group": {
                "_id": "$name",
                "uniqueIds": {"$push": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {
                "count": {"$gt": 1}
            }}
        ]
        duplicates = collection.aggregate(pipeline)
        for duplicate in duplicates:
            # 保留最新的文档，删除其他重复的文档
            # 假设_id越大，文档越新
            ids_to_delete = duplicate["uniqueIds"][:-1]  # 保留最后一个ID，即最新的文档
            if ids_to_delete:
                result = collection.delete_many({"_id": {"$in": ids_to_delete}})
                total_deleted += result.deleted_count

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_deleted > 0:
        log(f"步骤5运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤5运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def validate_references():
    # 实现需求6
    start_time = datetime.now()
    total_deleted = 0

    reference_fields = {
        "business_id": "business",
        "root_domain_id": "root_domain",
        "sub_domain_id": "sub_domain"
    }
    # 预加载引用数据
    ref_data = {ref: set(db[ref].distinct("_id")) for ref in reference_fields.values()}

    collections_to_validate = db.list_collection_names()
    for collection_name in collections_to_validate:
        collection = db[collection_name]
        ids_to_delete = []
        for field, ref_collection_name in reference_fields.items():
            if ref_collection_name not in ref_data:
                continue
            documents = collection.find({field: {"$exists": True, "$ne": None}}, {"_id": 1, field: 1})
            for document in documents:
                ref_id = document[field]
                # 尝试将引用字段的值转换为ObjectId
                try:
                    ref_id = ObjectId(ref_id)
                except:
                    ids_to_delete.append(document["_id"])
                    continue
                if ref_id not in ref_data[ref_collection_name]:
                    ids_to_delete.append(document["_id"])
        # 批量删除无效引用的文档
        if ids_to_delete:
            result = collection.delete_many({"_id": {"$in": ids_to_delete}})
            total_deleted += result.deleted_count

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 输出总计数
    if total_deleted > 0:
        log(f"步骤6运行耗时：{int(elapsed_time // 60)} m {int(elapsed_time % 60)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤6运行耗时：{int(elapsed_time // 60)} m {int(elapsed_time % 60)} s，未发现需要处理的文档。")

def remove_ipv4_names():
    # 实现新增需求7
    start_time = datetime.now()
    total_deleted = 0  # 初始化删除文档的总数

    ipv4_pattern = r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"

    collections_to_clean = ["root_domain", "sub_domain"]
    for collection_name in collections_to_clean:
        collection = db[collection_name]
        result = collection.delete_many({"name": {"$regex": ipv4_pattern}})
        deleted_count = result.deleted_count
        total_deleted += deleted_count
        if deleted_count > 0:
            log(f"集合 '{collection_name}': 删除了 {deleted_count} 个名称为IPv4地址的文档。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
    if total_deleted > 0:
        log(f"步骤7运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤7运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def replace_nan_content():
    # 实现新增需求8
    start_time = datetime.now()
    total_updated = 0  # 初始化更新文档的总数
    
    collections_to_update = db.list_collection_names()
    for collection_name in collections_to_update:
        collection = db[collection_name]
        query = {"$or": [{"notes": {"$regex": r"\"NaN\""}}, {"name": {"$regex": r"\"NaN\""}}]}
        update = {"$set": {"notes": "set by soapffz by clean", "name": "set by soapffz by clean"}}
        result = collection.update_many(query, update)
        if result.modified_count > 0:
            total_updated += result.modified_count
            log(f"集合 {collection_name} 替换了 {result.modified_count} 个文档中的NaN内容。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

if __name__ == "__main__":
    log("开始执行数据库清洗...")
    clean_empty_fields()
    convert_id_to_string()
    set_default_notes()
    ensure_time_fields()
    ensure_unique_name()
    validate_references()
    remove_ipv4_names()
    replace_nan_content()
    log("数据库清洗完成。")
