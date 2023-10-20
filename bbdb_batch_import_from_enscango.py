"""
作者：soapffz
创建时间：2023年10月1日
最后修改时间：2023年10月1日

脚本功能：从enscango导出的xlsx批量读取到bbdb中，需要传入文件名称和business_name
"""

import os
import pandas as pd
import re
import yaml
from pymongo import MongoClient, UpdateOne, InsertOne
from bson import ObjectId
from datetime import datetime

# 读取配置文件
with open("config_product.yaml", "r") as f:
    config = yaml.safe_load(f)


def process_data(db, xlsx_file_name, business_name):
    # 一次性读取business表到内存中
    try:
        business_collection = db["business"]
        business_data = list(business_collection.find())
    except Exception as e:
        print(f"读取business表时发生错误：{e}")
        exit(1)

    # 检查xlsx文件和business_name是否存在
    if not os.path.exists(xlsx_file_name):
        print(f"文件不存在：{xlsx_file_name}")
        exit(1)
    business = next((b for b in business_data if b["name"] == business_name), None)
    if not business:
        business = {
            "name": business_name,
            "company": [],
            "create_time": datetime(2023, 10, 1),
            "update_time": datetime.now(),
        }
        business_collection.insert_one(business)
    business_id = business["_id"]

    # 读取Excel文件
    try:
        df_app = pd.read_excel(xlsx_file_name, sheet_name="APP")
        df_wechat = pd.read_excel(xlsx_file_name, sheet_name="微信公众号")
        df_icp = pd.read_excel(xlsx_file_name, sheet_name="ICP备案")
        df_software = pd.read_excel(xlsx_file_name, sheet_name="软件著作权")
        df_company = pd.read_excel(xlsx_file_name, sheet_name="企业信息")
    except Exception as e:
        print(f"读取Excel文件时发生错误：{e}")
        exit(1)

    # 提取公司名称并插入到business表的company列表中
    new_companies = []
    for _, row in df_company.iterrows():
        if "企业名称" not in row or pd.isnull(row["企业名称"]) or row["经营状态"] == "注销":
            continue
        company_name = row["企业名称"]
        if company_name not in business["company"]:
            new_companies.append(company_name)

    # 批量更新business表
    if new_companies:
        business["company"].extend(new_companies)
        business["update_time"] = business.get("update_time") or datetime.now()
        business["create_time"] = business.get("create_time") or datetime(2023, 10, 1)
        business_collection.update_one(
            {"_id": business_id},
            {
                "$set": {
                    "company": business["company"],
                    "create_time": business["create_time"],
                },
                "$currentDate": {"update_time": True},
            },
        )

    # 插入APP数据
    operations = []
    for _, row in df_app.iterrows():
        if "名称" not in row or pd.isnull(row["名称"]):
            continue
        operation = UpdateOne(
            {"name": row["名称"]},
            {
                "$setOnInsert": {
                    "name": row.get("名称"),
                    "notes": row.get("简介"),
                    "avatar_pic_url": row.get("logo"),
                    "business_id": business_id,
                    "create_time": datetime(2023, 10, 1),
                },
                "$currentDate": {"update_time": True},
            },
            upsert=True,
        )
        operations.append(operation)
    if operations:
        db["app"].bulk_write(operations)

    # 插入微信公众号数据
    operations = []
    for _, row in df_wechat.iterrows():
        if "ID" not in row or pd.isnull(row["ID"]):
            continue
        operation = UpdateOne(
            {"wechatid": row["ID"]},
            {
                "$setOnInsert": {
                    "name": row.get("名称"),
                    "notes": row.get("简介", "import from enscango by soapffz"),
                    "avatar_pic_url": row.get("logo"),
                    "business_id": business_id,
                    "create_time": datetime(2023, 10, 1),
                },
                "$currentDate": {"update_time": True},
            },
            upsert=True,
        )
        operations.append(operation)
    if operations:
        db["wechat_public_account"].bulk_write(operations)

    # 插入ICP备案数据到root_domain表
    operations = []
    for _, row in df_icp.iterrows():
        if "域名" not in row or pd.isnull(row["域名"]):
            continue
        domain_name = row["域名"]
        existing_domain = db["root_domain"].find_one({"name": domain_name})
        if existing_domain is None:
            operation = InsertOne(
                {
                    "name": domain_name,
                    "icpregnum": row.get("网站备案/许可证号"),
                    "company": row.get("公司名称"),
                    "notes": "import from enscango by soapffz",
                    "business_id": business_id,
                    "create_time": datetime(2023, 10, 1),
                    "update_time": datetime.now(),
                }
            )
            operations.append(operation)
    if operations:  # 新增的检查
        db["root_domain"].bulk_write(operations)

    # 插入软件著作权数据
    operations = []
    for _, row in df_software.iterrows():
        if "软件名称" not in row or pd.isnull(row["软件名称"]):
            continue
        operation = UpdateOne(
            {"name": row["软件名称"]},
            {
                "$setOnInsert": {
                    "name": row["软件名称"],
                    "notes": row.get("软件简介"),
                    "regnumber": row.get("登记号"),
                    "type": row.get("分类"),
                    "business_id": business_id,
                    "create_time": datetime(2023, 10, 1),
                },
                "$currentDate": {"update_time": True},
            },
            upsert=True,
        )
        operations.append(operation)
    if operations:
        db["software_copyright"].bulk_write(operations)


if __name__ == "__main__":
    # 连接MongoDB
    mongodb_uri = config["DEFAULT"].get("BBDB_MONGODB_URI")
    try:
        client = MongoClient(mongodb_uri)
        db = client["bbdb"]
    except Exception as e:
        print(f"连接MongoDB时发生错误：{e}")
        exit(1)

    # 传入xlsx文件名称和对应的business_name
    xlsx_file_name = "outs/【合并】--2023-10-18--1697641169.xlsx"
    business_name = "国内-招商银行"

    # 处理数据并插入到数据库
    process_data(db, xlsx_file_name, business_name)
