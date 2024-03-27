"""
new Env('根据bbdb已有根域名导入文本内容');
* * * * * https://raw.githubusercontent.com/soapffz/bbdbscripts//main/bbdb_new_subdomain_site_in_txt_to_bbdb.py

文件名: debug_bbdb_new_subdomain_site_in_txt_to_bbdb.py
作者: soapffz
创建日期: 2024年3月26日
最后修改日期: 2024年3月28日

在已有根域名的情况下，从文本文件解析尝试插入子域名和站点，支持ip格式的URL，注意一定要处理好文本文件

"""

import re
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

# MongoDB连接信息
mongo_uri = "mongodb://192.168.2.188:27017/"

# 连接到MongoDB
client = MongoClient(mongo_uri)
db = client["bbdb"]


def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(
        f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}"
    )


def preprocess_lines(lines):
    processed_lines = []
    for line in lines:
        line = line.strip()
        if line:
            if "." not in line:
                continue
            # 去除以*.开头的域名
            line = re.sub(r"^\*\.", "", line)
            # 处理如果开头直接是*加上域名的情况，去除*
            line = re.sub(r"^\*", "", line)
            processed_lines.append(line)
    return processed_lines


def preprocess_url(url):
    # 使用正则表达式匹配URL
    url_match = re.match(r"^(https?://)?([\w\.-]+?)(:\d+)?(/.*)?$", url)
    if url_match:
        scheme = url_match.group(1)
        hostname = url_match.group(2)
        port = url_match.group(3) or ""
        path = url_match.group(4) or ""
        # 重构URL，确保其结构正确
        processed_url = f"{scheme}{hostname}{port}{path}"
        return processed_url, scheme, hostname
    else:
        # 如果URL格式不正确，返回None和空字符串作为scheme
        return None, "", ""


def parse_and_process(lines, business_name=""):
    # 如果business_name不为空，则查询对应的business_id
    business_id_filter = {}
    if business_name:
        business = db.business.find_one({"name": business_name})
        if business:
            business_id_filter = {"business_id": str(business["_id"])}
        else:
            log_message(
                f"Business name '{business_name}' not found.", is_positive=False
            )
            return

    sub_domains = list(db.sub_domain.find(business_id_filter))
    sub_domains_dict = {
        str(sub_domain["_id"]): sub_domain for sub_domain in sub_domains
    }

    root_domains = list(db.root_domain.find(business_id_filter))
    root_domains_dict = {
        str(root_domain["_id"]): root_domain for root_domain in root_domains
    }
    root_domains_set = {doc["name"] for doc in root_domains}
    ips = list(db.ip.find(business_id_filter))
    ips_dict = {ip["address"]: ip for ip in ips}
    sub_domains_to_insert = []
    sites_to_insert = []

    blacklist_sub_domains = set(
        doc["name"]
        for doc in db.blacklist.find({"type": "sub_domain", **business_id_filter})
    )
    blacklist_urls = set(
        doc["name"] for doc in db.blacklist.find({"type": "url", **business_id_filter})
    )
    blacklist_ips = set(
        doc["name"] for doc in db.blacklist.find({"type": "ip", **business_id_filter})
    )
    existing_root_domains = set(
        doc["name"] for doc in db.root_domain.find(business_id_filter)
    )
    existing_sub_domains = set(
        doc["name"] for doc in db.sub_domain.find(business_id_filter)
    )
    existing_sites = set(doc["name"] for doc in db.site.find(business_id_filter))
    log_message("加载数据库完成")

    lines = preprocess_lines(lines)
    log_message("文本文件读取完成")
    # log_message(lines)

    # 解析根域名
    for line in lines:
        if line.startswith("http"):
            continue
        root_domain_match = re.search(r"^(.*?\.\w+)\.\w+$", line)
        if root_domain_match:
            root_domain = root_domain_match.group()
            if (
                root_domain in root_domains_set
                and root_domain not in blacklist_sub_domains
            ):
                root_domain_obj = next(
                    (doc for doc in root_domains if doc["name"] == root_domain), None
                )
                root_domain_id = str(root_domain_obj["_id"])
                business_id = str(root_domain_obj["business_id"])

                # 解析子域名
                sub_domain = line.split(root_domain)[0].rstrip(".")
                if (
                    sub_domain != root_domain
                    and sub_domain not in blacklist_sub_domains
                    and sub_domain not in existing_sub_domains
                    and sub_domain != ""
                ):
                    sub_domain_data = {
                        "name": sub_domain,
                        "notes": "set by soapffz with script",
                        "root_domain_id": root_domain_id,
                        "business_id": business_id,
                        "create_time": datetime.utcnow(),
                        "update_time": datetime.utcnow(),
                    }
                    sub_domains_to_insert.append(sub_domain_data)

    # 加载子域名数据，将根域名和子域名合并在一起来判断URL的归属
    sub_domains = list(db.sub_domain.find(business_id_filter))
    domain_names = {sub_domain["name"]: sub_domain for sub_domain in sub_domains}
    domain_names.update(
        {root_domain["name"]: root_domain for root_domain in root_domains}
    )

    # 解析站点信息
    for line in lines:
        # 匹配 HTTP/HTTPS 协议头或纯域名
        processed_url, scheme, hostname = preprocess_url(line)
        if processed_url and scheme:
            if scheme.startswith("http://") or scheme.startswith("https://"):
                # 处理 IP 地址形式的 URL
                if re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
                    ip_address = hostname
                    if ip_address not in blacklist_ips:
                        ip_docs = ips_dict.get(ip_address)
                        if ip_docs:
                            if "sub_domain_id" in ip_docs:
                                sub_domain_id = str(ip_docs["sub_domain_id"])
                            else:
                                sub_domain_id = None
                            root_domain_id = str(ip_docs["root_domain_id"])
                            business_id = str(ip_docs["business_id"])
                            hostname = (
                                sub_domains_dict[sub_domain_id]["name"]
                                if sub_domain_id in sub_domains_dict
                                else (
                                    root_domains_dict[root_domain_id]["name"]
                                    if root_domain_id in root_domains_dict
                                    else ""
                                )
                            )
                            if (
                                processed_url not in blacklist_urls
                                and processed_url not in existing_sites
                            ):
                                site_data = {
                                    "name": processed_url,
                                    "status": "",
                                    "title": "",
                                    "hostname": hostname,
                                    "ip": ip_address,
                                    "http_server": "",
                                    "body_length": "",
                                    "headers": "",
                                    "keywords": "",
                                    "applications": [],
                                    "applications_categories": [],
                                    "applications_types": [],
                                    "applications_levels": [],
                                    "application_manufacturer": [],
                                    "fingerprint": [],
                                    "root_domain_id": root_domain_id,
                                    "sub_domain_id": sub_domain_id,
                                    "business_id": business_id,
                                    "notes": "set by soapffz with script",
                                    "create_time": datetime.now(
                                        timezone(timedelta(hours=8))
                                    ),
                                    "update_time": datetime.now(
                                        timezone(timedelta(hours=8))
                                    ),
                                }
                                sites_to_insert.append(site_data)

                # 处理域名形式的 URL
                else:
                    domain_info = None
                    for domain_name, domain_doc in domain_names.items():
                        if hostname.endswith(domain_name):
                            domain_info = domain_doc
                            break

                    if domain_info:
                        root_domain_id = (
                            str(domain_info["_id"])
                            if "root_domain_id" not in domain_info
                            else domain_info["root_domain_id"]
                        )
                        sub_domain_id = (
                            None
                            if "root_domain_id" not in domain_info
                            else str(domain_info["_id"])
                        )
                        business_id = domain_info["business_id"]

                        if (
                            processed_url not in blacklist_urls
                            and processed_url not in existing_sites
                        ):
                            site_data = {
                                "name": processed_url,
                                "status": "",
                                "title": "",
                                "hostname": hostname,
                                "ip": "",
                                "http_server": "",
                                "body_length": "",
                                "headers": "",
                                "keywords": "",
                                "applications": [],
                                "applications_categories": [],
                                "applications_types": [],
                                "applications_levels": [],
                                "application_manufacturer": [],
                                "fingerprint": [],
                                "root_domain_id": root_domain_id,
                                "business_id": business_id,
                                "notes": "set by soapffz with script",
                                "create_time": datetime.now(
                                    timezone(timedelta(hours=8))
                                ),
                                "update_time": datetime.now(
                                    timezone(timedelta(hours=8))
                                ),
                            }
                            if sub_domain_id:
                                site_data["sub_domain_id"] = sub_domain_id
                            sites_to_insert.append(site_data)

    # 批量插入数据
    if sub_domains_to_insert:
        db.sub_domain.insert_many(sub_domains_to_insert)
        # log_message(sub_domains_to_insert)
        log_message(f"Inserted {len(sub_domains_to_insert)} sub domains.")
    if sites_to_insert:
        db.site.insert_many(sites_to_insert)
        # log_message(sites_to_insert)
        log_message(f"Inserted {len(sites_to_insert)} sites.")


def main():
    log_message("开始解析文件...")
    with open("domain.txt", "r") as file:
        lines = file.readlines()

    # 处理可以指定business，但是也不会添加新的根域名，只是限定了范围速度会更快,插入的站点一直可以属于根域名，也可以属于子域名
    business_name = ""
    parse_and_process(lines, business_name)
    # parse_and_process(lines)
    log_message("解析完成!")


if __name__ == "__main__":
    main()
