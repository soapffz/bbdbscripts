"""
作者：soapffz
创建时间：2023年10月1日
最后修改时间：2024年3月21日

脚本功能：从enscango导出的xlsx批量读取到bbdb中，需要传入文件名称和business_name
"""

import os
import pandas as pd
import re
from pymongo import MongoClient, UpdateOne, InsertOne
from bson import ObjectId
from datetime import datetime
import re


def is_ipv4(address):
    """
    检查给定的字符串是否为有效的IPv4地址。
    """
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    return re.match(pattern, address) is not None


def read_excel_sheet(xlsx_file_name, sheet_name):
    """
    尝试读取指定的Excel sheet，如果不存在则返回空的DataFrame。
    """
    try:
        return pd.read_excel(xlsx_file_name, sheet_name=sheet_name)
    except ValueError:
        print(f"{sheet_name} sheet不存在，跳过。")
        return pd.DataFrame()


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
            "create_time": datetime.now(),
            "update_time": datetime.now(),
        }
        business_collection.insert_one(business)
    business_id = business["_id"]

    # 读取Excel文件
    # 使用封装的函数读取各个sheet
    df_app = read_excel_sheet(xlsx_file_name, "APP")
    df_wechat = read_excel_sheet(xlsx_file_name, "微信公众号")
    df_icp = read_excel_sheet(xlsx_file_name, "ICP备案")
    df_software = read_excel_sheet(xlsx_file_name, "软件著作权")
    df_company = read_excel_sheet(xlsx_file_name, "企业信息")

    # 提取公司名称并插入到business表的company列表中
    new_companies = []
    for _, row in df_company.iterrows():
        if (
            "企业名称" not in row
            or pd.isnull(row["企业名称"])
            or row["经营状态"] == "注销"
        ):
            continue
        company_name = row["企业名称"]
        if company_name not in business["company"]:
            new_companies.append(company_name)

    # 批量更新business表
    if new_companies:
        business["company"].extend(new_companies)
        business["update_time"] = business.get("update_time") or datetime.now()
        business["create_time"] = business.get("create_time") or datetime.now()
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
        notes = row.get("简介")
        if pd.isnull(notes) or notes == "":
            notes = "set by soapffz manually"
        operation = UpdateOne(
            {"name": row["名称"]},
            {
                "$setOnInsert": {
                    "name": row.get("名称"),
                    "notes": notes,
                    "avatar_pic_url": row.get("logo"),
                    "business_id": business_id,
                    "create_time": datetime.now(),
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
        notes = row.get("描述")
        if pd.isnull(notes) or notes == "":
            notes = "set by soapffz manually"
        operation = UpdateOne(
            {"wechatid": row["ID"]},
            {
                "$setOnInsert": {
                    "name": row.get("名称"),
                    "notes": notes,
                    "avatar_pic_url": row.get("LOGO"),
                    "wechat_public_pic_url": row.get("二维码"),
                    "business_id": business_id,
                    "create_time": datetime.now(),
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
        domain_name = row.get("域名")
        if pd.isnull(domain_name) or is_ipv4(domain_name):
            continue  # 如果是IPv4地址，则跳过
        existing_domain = db["root_domain"].find_one({"name": domain_name})
        if existing_domain is None:
            company = row.get("公司名称")
            if pd.isnull(company) or company == "":
                company = ""
            operation = InsertOne(
                {
                    "name": domain_name,
                    "icpregnum": row.get("网站备案/许可证号"),
                    "company": company,
                    "notes": "import from enscango by soapffz",
                    "business_id": business_id,
                    "create_time": datetime.now(),
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
        notes = row.get("简介")
        if pd.isnull(notes) or notes == "":
            notes = "set by soapffz manually"
        operation = UpdateOne(
            {"name": row["软件名称"]},
            {
                "$setOnInsert": {
                    "name": row["软件名称"],
                    "notes": notes,
                    "regnumber": row.get("登记号"),
                    "type": row.get("分类"),
                    "business_id": business_id,
                    "create_time": datetime.now(),
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
    mongodb_uri = "mongodb://192.168.2.188:27017/"
    try:
        client = MongoClient(mongodb_uri)
        db = client["bbdb"]
    except Exception as e:
        print(f"连接MongoDB时发生错误：{e}")
        exit(1)

    # 传入xlsx文件名称和对应的business_name
    xlsx_file_name = (
        "outs/浙江永康农村商业银行股份有限公司--2024-03-21--1711028041.xlsx"
    )
    business_name = "国内-雷神众测-永康农商银行"

    # 处理数据并插入到数据库
    process_data(db, xlsx_file_name, business_name)
