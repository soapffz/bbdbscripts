"""
文件名: bbdb_update_by_git_trickest_inventory.py
作者: soapffz
创建日期: 2024年3月19日
最后修改日期: 2024年3月19日

1. 在脚本运行之前先在/ql目录git clone https://github.com/trickest/inventory.git git_trickest_inventory
2. 本脚本处理所有子文件夹中的hostnames.txt和servers.txt文件，将新发现内容写入对应表中
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from urllib.parse import urlparse

def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

def extract_domain(hostname, valid_domains, current_root_domain=None):
    """从hostname中提取根域名，并可选地验证是否与当前处理的根域名匹配"""
    parts = hostname.split('.')
    for i in range(2, len(parts) + 1):
        potential_domain = '.'.join(parts[-i:])
        if potential_domain in valid_domains:
            if current_root_domain and potential_domain == current_root_domain:
                return None
            return potential_domain
    return None

def process_hostnames(file_path, domain_to_folder, valid_domains):
    """处理hostnames.txt文件，记录域名与文件夹的关联关系"""
    with open(file_path, 'r') as f:
        hostnames = set(f.read().strip().split('\n'))
        for hostname in hostnames:
            root_domain_name = extract_domain(hostname, valid_domains)
            if root_domain_name and root_domain_name not in domain_to_folder:
                domain_to_folder[root_domain_name] = os.path.basename(os.path.dirname(file_path))

def process_files_and_write_to_db(domain_to_folder, db, valid_domains, blacklist_sub_domains, blacklist_urls, sub_domains, existing_sites, git_folder):
    """处理hostnames.txt和servers.txt文件，并将新发现的子域名和站点信息写入数据库"""
    for root_domain_name, folder in domain_to_folder.items():
        root_domain = db.root_domain.find_one({"name": root_domain_name})
        if not root_domain:
            log_message(f"根域名 {root_domain_name} 未在数据库中找到，跳过。", False)
            continue
        root_domain_id_str = str(root_domain['_id'])
        business_id_str = str(root_domain['business_id'])

        # 处理 hostnames.txt
        hostnames_file_path = os.path.join(git_folder, folder, "hostnames.txt")
        if os.path.exists(hostnames_file_path) and os.path.getsize(hostnames_file_path) > 0:
            with open(hostnames_file_path, 'r') as file:
                hostnames = file.read().strip().split('\n')
                new_subdomains = set()
                for hostname in hostnames:
                    if extract_domain(hostname, valid_domains, root_domain_name) and hostname not in sub_domains[root_domain_id_str] and hostname not in blacklist_sub_domains:
                        new_subdomains.add(hostname)

                existing_subdomains = {sub['name'] for sub in db.sub_domain.find({"root_domain_id": root_domain_id_str})}
                new_subdomains -= existing_subdomains

                if not new_subdomains:
                    log_message(f"根域名 {root_domain_name} 没有新的子域名需要添加。")
                else:
                    new_subdomain_docs = [{
                        "name": subdomain,
                        "icpregnum": "",
                        "company": "",
                        "company_type": "",
                        "root_domain_id": root_domain_id_str,
                        "business_id": business_id_str,
                        "notes": "set by script with ql",
                        "create_time": datetime.now(timezone(timedelta(hours=8))),
                        "update_time": datetime.now(timezone(timedelta(hours=8)))
                    } for subdomain in new_subdomains]
                    db.sub_domain.insert_many(new_subdomain_docs)
                    log_message(f"根域名 {root_domain_name} 插入了 {len(new_subdomain_docs)} 个新的子域名。")

        # 处理 servers.txt
        servers_file_path = os.path.join(git_folder, folder, "servers.txt")
        new_sites = []
        if os.path.exists(servers_file_path) and os.path.getsize(servers_file_path) > 0:
            with open(servers_file_path, 'r') as file:
                urls = file.read().strip().split('\n')
                for url in urls:
                    parsed_url = urlparse(url)
                    hostname = parsed_url.hostname
                    if hostname and ((hostname == root_domain_name or hostname in sub_domains[root_domain_id_str]) and url not in existing_sites and url not in blacklist_urls):
                        sub_domain = db.sub_domain.find_one({"name": hostname, "root_domain_id": root_domain_id_str})
                        sub_domain_id_str = str(sub_domain['_id']) if sub_domain else ""
                        site_doc = {
                            "name": url,
                            "status": "",
                            "title": "",
                            "hostname": hostname,
                            "ip": "",
                            "http_server": "",
                            "body_length": "",
                            "headers": "",
                            "keywords": [],
                            "applications": [],
                            "applications_categories": [],
                            "applications_types": [],
                            "applications_levels": [],
                            "application_manufacturer": [],
                            "fingerprint": [],
                            "root_domain_id": root_domain_id_str,
                            "sub_domain_id": sub_domain_id_str,
                            "business_id": business_id_str,
                            "notes": "set by script with ql",
                            "create_time": datetime.now(timezone(timedelta(hours=8))),
                            "update_time": datetime.now(timezone(timedelta(hours=8)))
                        }
                        new_sites.append(site_doc)

            if new_sites:
                db.site.insert_many(new_sites)
                log_message(f"根域名 {root_domain_name} 插入了 {len(new_sites)} 个新的站点。")

def main():
    git_folder = "/ql/git_trickest_inventory"
    BBDB_MONGOURI = os.getenv("BBDB_MONGOURI")
    client = MongoClient(BBDB_MONGOURI)
    db = client.bbdb
    log_message("数据库连接成功")

    valid_domains = {item['name'] for item in db.root_domain.find()}
    blacklist = {item['name'] for item in db.blacklist.find({"type": {"$in": ["sub_domain", "url"]}})}
    blacklist_sub_domains = {item['name'] for item in db.blacklist.find({"type": "sub_domain"})}
    blacklist_urls = {item['name'] for item in db.blacklist.find({"type": "url"})}

    domain_to_folder = {}
    # 修改sub_domains的构建逻辑，使其映射根域名ID到子域名列表
    sub_domains = {}
    for sub_domain in db.sub_domain.find():
        root_domain_id_str = str(sub_domain['root_domain_id'])
        if root_domain_id_str not in sub_domains:
            sub_domains[root_domain_id_str] = []
        sub_domains[root_domain_id_str].append(sub_domain['name'])

    existing_sites = {item['name'] for item in db.site.find()}

    # 建立域名与文件夹的关联关系
    for subdir, dirs, files in os.walk(git_folder):
        for file in files:
            if file == "hostnames.txt":
                file_path = os.path.join(subdir, file)
                process_hostnames(file_path, domain_to_folder, valid_domains)

    log_message(f"域名与文件夹的关联关系处理完毕，共有 {len(domain_to_folder)} 对关联关系")

    # 处理hostnames.txt和servers.txt文件，并将新发现的子域名和站点信息写入数据库
    process_files_and_write_to_db(domain_to_folder, db, valid_domains, blacklist_sub_domains, blacklist_urls, sub_domains, existing_sites, git_folder)

    log_message("所有操作完成。")

if __name__ == "__main__":
    main()
