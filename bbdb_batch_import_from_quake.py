"""
new Env('Quake数据导入bbdb');
* * * * * https://raw.githubusercontent.com/soapffz/bbdbscripts/main/bbdb_batch_import_from_quake.py

文件名: bbdb_batch_import_from_quake.py
作者: soapffz
创建日期: 2023年10月15日
最后修改日期: 2023年3月26日

这个脚本用于从Excel文件中读取数据，并将数据导入到MongoDB数据库中。它首先会连接到MongoDB，然后查询business表。如果找不到指定的business，脚本会停止运行。然后，脚本会读取Excel文件，并处理文件中的数据。它会移除单元格值开头的单引号，并提取绝对根域名和子域名。如果在数据库中找不到对应的root_domain或sub_domain，脚本会创建新的记录。然后，脚本会准备site表和ip表的数据，并插入到数据库中。在处理数据的过程中，脚本会处理URL，移除:443和:80，并将'keywords', 'applications', 'applications_categories', 'applications_types', 'applications_levels', 'application_manufacturer'这些字段的值转换为列表，并将嵌套的列表展平为一级列表。如果在处理过程中遇到错误，脚本会打印错误信息并跳过当前列。
"""
import os
import pandas as pd
from pymongo import MongoClient
import ast
import re
from datetime import datetime, timedelta, timezone

def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "\[ + \]" if is_positive else "\[ - \]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

def flatten(lst):
    """辅助函数,用于展平嵌套的列表"""
    result = []
    for i in lst:
        if isinstance(i, list):
            result.extend(flatten(i))
        else:
            result.append(i)
    return result

def process_domain(domain, icpregnum, company, db):
    """处理域名相关数据"""
    pattern = r"[\w-]+\.[\w-]+$"
    match = re.search(pattern, domain)
    if match:
        root_domain_name = match.group()
        root_domain = db.root_domain.find_one({"name": root_domain_name})
        if root_domain is None:
            root_domain_id = db.root_domain.insert_one(
                {
                    "name": root_domain_name,
                    "icpregnum": icpregnum,
                    "company": company,
                    "create_time": datetime.now(),
                    "update_time": datetime.now(),
                }
            ).inserted_id
        else:
            root_domain_id = root_domain["_id"]

        if root_domain_name != domain:
            sub_domain = db.sub_domain.find_one({"name": domain})
            if sub_domain is None:
                sub_domain_id = db.sub_domain.insert_one(
                    {
                        "name": domain,
                        "root_domain_id": root_domain_id,
                        "icpregnum": icpregnum,
                        "company": company,
                        "create_time": datetime.now(),
                        "update_time": datetime.now(),
                    }
                ).inserted_id
            else:
                sub_domain_id = sub_domain["_id"]
        else:
            sub_domain_id = None

        return root_domain_id, sub_domain_id

def process_site_data(df, business_id, root_domain_id, sub_domain_id, db):
    """处理站点数据"""
    log_message("Preparing the site data...")
    site_data = df[
        [
            "URL",
            "网站状态码",
            "网页标题",
            "网站关键词",
            "应用名称",
            "应用类别",
            "应用类型",
            "应用层级",
            "应用生产厂商",
        ]
    ].copy()
    site_data.columns = [
        "url",
        "status",
        "title",
        "keywords",
        "applications",
        "applications_categories",
        "applications_types",
        "applications_levels",
        "application_manufacturer",
    ]
    site_data["business_id"] = business_id
    site_data["root_domain_id"] = root_domain_id
    site_data["sub_domain_id"] = sub_domain_id

    # 处理URL,移除:443和:80
    site_data["url"] = site_data["url"].apply(lambda x: re.sub(r":443$|:80$", "", x))

    # 将字符串转换为列表,并将嵌套的列表展平为一级列表。如果在处理过程中遇到错误,它会打印错误信息并跳过当前列。
    columns_to_process = [
        "keywords",
        "applications",
        "applications_categories",
        "applications_types",
        "applications_levels",
        "application_manufacturer",
    ]
    for column in columns_to_process:
        if column == "keywords":
            site_data[column] = site_data[column].apply(
                lambda x: list(set(re.split(r"\n|,|、|/|，", x))) if pd.notnull(x) else []
            )
        else:
            try:
                site_data[column] = site_data[column].apply(
                    lambda x: flatten(ast.literal_eval(str(x))) if pd.notnull(x) else []
                )
            except Exception as e:
                log_message(f"Error processing column {column}: {e}", is_positive=False)
                continue

    # 插入数据到site表
    log_message("Inserting data into the site table...")
    db.site.insert_many(site_data.to_dict("records"))

def batch_import_from_quake_to_bbdb(xlsx_name, business_name):
    log_message(f"Starting the import process for {business_name}...")

    # 连接到MongoDB
    mongodb_uri = os.getenv("BBDB_MONGOURI")
    client = MongoClient(mongodb_uri)
    db = client["bbdb"]

    # 查询business表
    log_message("Looking for business in the database...")
    business = db.business.find_one({"name": business_name})
    if business is None:
        log_message(f"No business found with name {business_name}", is_positive=False)
        return
    business_id = business["_id"]

    # 读取xlsx文件
    log_message("Reading the Excel file...")
    df = pd.read_excel(xlsx_name)

    # 移除单元格值开头的单引号
    log_message("Processing the data in the Excel file...")
    df = df.applymap(lambda x: x[1:] if isinstance(x, str) and x.startswith("'") else x)

    # 提取绝对根域名和子域名,并获取或创建对应的_id
    log_message("Processing the domain data...")
    for index, row in df.iterrows():
        domain = row["网站Host（域名）"]
        icpregnum = row["ICP备案编号"] if pd.notnull(row["ICP备案编号"]) else ""
        company = row["ICP备案单位"] if pd.notnull(row["ICP备案单位"]) else ""
        root_domain_id, sub_domain_id = process_domain(domain, icpregnum, company, db)

        # 处理站点数据
        process_site_data(df, business_id, root_domain_id, sub_domain_id, db)

    # 准备ip表的数据
    log_message("Preparing the IP data...")
    ip_data = df[
        [
            "IP地址",
            "端口号",
            "服务名称",
            "省份（中文）",
            "城市（中文）",
            "国家（中文）",
            "区县（英文）",
            "区县（中文）",
            "省份（英文）",
            "城市（英文）",
            "国家（英文）",
            "运营商",
        ]
    ].copy()
    ip_data.columns = [
        "address",
        "port",
        "service_name",
        "province_cn",
        "city_cn",
        "country_cn",
        "districts_and_counties_en",
        "districts_and_counties_cn",
        "province_en",
        "city_en",
        "country_en",
        "operators",
    ]
    ip_data["business_id"] = business_id

    # 插入数据到ip表
    log_message("Inserting data into the IP table...")
    db.ip.insert_many(ip_data.to_dict("records"))

    log_message("Data imported successfully")

if __name__ == "__main__":
    batch_import_from_quake_to_bbdb("服务数据_20231014_214410.xlsx", "国内-教育src")
