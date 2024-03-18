"""
文件名: bbdb_clean.py
作者: soapffz
创建日期: 2023年10月1日
最后修改日期: 2024年3月18日

以下清洗步骤建议不要调换顺序

1.删除所有表中有business_id、root_domain_id、sub_domain_id任何一个字段，但是其中任何一个字段为空的文档。
2.将所有表中有business_id、root_domain_id、sub_domain_id字段，但是格式不是为string类型，而是ObjectId类型的地方转化为string类型。
3.所有表中notes字段为空的文档，都将其设置为"set by soapffz"。
4.每个表都必须有create_time和update_time字段，如果没有则创建，如果为空也将两个字段都设置为当前时间的北京时间。
5.所有表中的name字段都应保持唯一，删除所有name字段重复的较老文档。
6.使用business_id、root_domain_id、sub_domain_id去相应表中查找，但是没有查找到对应文档的文档，查找逻辑为business_id为business表中的_id，root_domain_id为root_domain表中的_id，sub_domain_id为sub_domain的_id。
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

    # 根据处理的文档数量和耗时，输出相应的日志
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
            log(f"集合 {collection_name} 转换了 {len(updates)} 个文档中的ObjectId为字符串。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
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
        if result.modified_count > 0:
            total_updated += result.modified_count
            log(f"集合 {collection_name} 为 {result.modified_count} 个文档设置了默认notes。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
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
            log(f"集合 {collection_name} 更新了 {len(updates)} 个文档的时间字段。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
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
                deleted_count = result.deleted_count
                total_deleted += deleted_count
                log(f"集合 '{collection_name}': 删除了 {deleted_count} 个重复的'name'字段文档。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
    if total_deleted > 0:
        log(f"步骤5运行耗时：{int(elapsed_time)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤5运行耗时：{int(elapsed_time)} s，未发现需要处理的文档。")

def validate_references():
    # 实现需求6，考虑到类型转换
    start_time = datetime.now()
    total_deleted = 0  # 初始化删除文档的总数

    reference_fields = {
        "business_id": "business",
        "root_domain_id": "root_domain",
        "sub_domain_id": "sub_domain"
    }
    collections_to_validate = db.list_collection_names()
    for collection_name in collections_to_validate:
        collection = db[collection_name]
        for field, ref_collection_name in reference_fields.items():
            # 检查引用集合是否存在
            if ref_collection_name not in collections_to_validate:
                log(f"引用的集合 '{ref_collection_name}' 不存在，跳过验证。", is_positive=False)
                continue
            ref_collection = db[ref_collection_name]
            documents = collection.find({field: {"$exists": True, "$ne": None}})
            ids_to_delete = []
            for document in documents:
                ref_id = document[field]
                # 尝试将引用字段的值转换为ObjectId，以匹配对应集合中的_id
                try:
                    ref_id = ObjectId(ref_id)
                except:
                    # 如果转换失败，记录该文档以便删除，因为无法匹配有效的ObjectId
                    ids_to_delete.append(document["_id"])
                    continue
                # 检查引用的文档是否存在
                if not ref_collection.find_one({"_id": ref_id}):
                    ids_to_delete.append(document["_id"])
            # 删除引用不正确的文档
            if ids_to_delete:
                result = collection.delete_many({"_id": {"$in": ids_to_delete}})
                deleted_count = result.deleted_count
                total_deleted += deleted_count
                log(f"集合 '{collection_name}': 删除了 {deleted_count} 个引用字段 '{field}' 不正确的文档。")

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # 根据处理的文档数量和耗时，输出相应的日志
    if total_deleted > 0:
        log(f"步骤6运行耗时：{int(elapsed_time // 60)} m {int(elapsed_time % 60)} s，共处理文档个数：{total_deleted}")
    else:
        log(f"步骤6运行耗时：{int(elapsed_time // 60)} m {int(elapsed_time % 60)} s，未发现需要处理的文档。")

if __name__ == "__main__":
    log("开始执行数据库清洗...")
    clean_empty_fields()
    convert_id_to_string()
    set_default_notes()
    ensure_time_fields()
    ensure_unique_name()
    validate_references()
    log("数据库清洗完成。")
