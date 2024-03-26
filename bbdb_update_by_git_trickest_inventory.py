"""
new Env('trickest_inventory');
*/6 * * * * https://raw.githubusercontent.com/soapffz/bbdbscripts/main/bbdb_update_by_git_trickest_inventory.py

文件名: bbdb_update_by_git_trickest_inventory.py
作者: soapffz
创建日期: 2024年3月19日
最后修改日期: 2024年3月20日

1. 在脚本运行之前先在/ql目录git clone https://github.com/trickest/inventory.git git_trickest_inventory
2. 本脚本处理所有子文件夹中的hostnames.txt和servers.txt文件，将新发现内容写入对应表中
3. 在处理 hostnames.txt 时，对于每个域名需要满足以下条件才能作为新子域名保存:
(1) 域名不在 blacklist_sub_domains 中
(2) 域名的根域名与当前处理的 root_domain_name 相同
(3) 域名不在 existing_sub_domains 中
4. 在处理 servers.txt 时，对于每个 URL，需要满足以下条件才能作为新站点保存:
(1) URL 不在 blacklist_urls 中
(2) 提取出的主机名 hostname 要么在 existing_sub_domains 中，要么与当前 root_domain_name 相同
(3) 该 URL 在站点表 site 中不存在
5. business_id、root_domain_id、sub_domain_id均为string类型，分别对应business表、root_domain表、sub_domain表对应文档的类型为ObjectID类型的_id，请注意转化
"""
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from urllib.parse import urlparse

def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

def extract_domain(hostname, current_root_domain=None):
    """从hostname中提取根域名，并可选地验证是否与当前处理的根域名匹配"""
    parts = hostname.split('.')
    if len(parts) > 1:
        potential_domain = '.'.join(parts[-2:])
        if current_root_domain and potential_domain == current_root_domain:
            return potential_domain
        return potential_domain
    return None

def load_db_data(db):
    """从数据库加载所有需要的数据到内存中"""
    root_domain_names = {domain['name'] for domain in db.root_domain.find()}
    blacklist_sub_domains = {item['name'] for item in db.blacklist.find({"type": "sub_domain"})}
    blacklist_urls = {item['name'] for item in db.blacklist.find({"type": "url"})}
    existing_sub_domains = {sub_domain['name']: str(sub_domain['root_domain_id']) for sub_domain in db.sub_domain.find({}, {"name": 1, "root_domain_id": 1})}
    return root_domain_names, blacklist_sub_domains, blacklist_urls, existing_sub_domains

def process_hostnames(file_path, domain_to_folder, root_domain_names):
    """处理hostnames.txt文件，记录域名与文件夹的关联关系"""
    folder_name = os.path.basename(os.path.dirname(file_path))
    with open(file_path, 'r') as f:
        hostnames = set(line.strip() for line in f)
        for hostname in hostnames:
            root_domain_name = extract_domain(hostname)
            if root_domain_name and root_domain_name in root_domain_names and root_domain_name not in domain_to_folder:
                domain_to_folder[root_domain_name] = folder_name

def process_files_and_write_to_db(domain_to_folder, db, git_folder, root_domain_names, blacklist_sub_domains, blacklist_urls, existing_sub_domains):
    new_subdomains = []
    new_sites = []
    for hostname, folder in domain_to_folder.items():
        root_domain_name = extract_domain(hostname)
        if root_domain_name not in root_domain_names:
            log_message(f"根域名 {root_domain_name} 未在数据库中找到，跳过。", False)
            continue
        log_message(f"正在处理根域名: {root_domain_name}")
        root_domain = db.root_domain.find_one({"name": root_domain_name})
        root_domain_id_str = str(root_domain['_id'])
        business_id_str = str(root_domain['business_id'])

        # 处理 hostnames.txt
        hostnames_file_path = os.path.join(git_folder, folder, "hostnames.txt")
        if os.path.exists(hostnames_file_path) and os.path.getsize(hostnames_file_path) > 0:
            if hostname not in existing_sub_domains.keys():
                new_subdomains.append({
                    "name": hostname,
                    "icpregnum": "",
                    "company": "",
                    "company_type": "",
                    "root_domain_id": root_domain_id_str,
                    "business_id": business_id_str,
                    "notes": "set by script with ql",
                    "create_time": datetime.now(timezone(timedelta(hours=8))),
                    "update_time": datetime.now(timezone(timedelta(hours=8)))
                })
        if new_subdomains:
            db.sub_domain.insert_many(new_subdomains)
            log_message(f"根域名 {root_domain_name} 插入了 {len(new_subdomains)} 个新的子域名。")
        else:
            log_message(f"根域名 {root_domain_name} 没有新的子域名需要添加。")
        new_subdomains = []  # 清空列表,准备处理下一个根域名

        # 处理 servers.txt
        servers_file_path = os.path.join(git_folder, folder, "servers.txt")
        if os.path.exists(servers_file_path) and os.path.getsize(servers_file_path) > 0:
            with open(servers_file_path, 'r') as file:
                servers = {line.strip() for line in file}
                for server in servers:
                    url = urlparse(server)
                    if url.scheme and url.netloc and server not in blacklist_urls:
                        hostname = url.netloc
                        if hostname in existing_sub_domains.keys() or hostname == root_domain_name:
                            sub_domain_id_str = existing_sub_domains.get(hostname, None)
                            existing_site = db.site.find_one({"name": server, "root_domain_id": root_domain_id_str})
                            if not existing_site:
                                new_sites.append({
                                    "name": server,
                                    "status": "",
                                    "title": "",
                                    "hostname": "",
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
                                })
        if new_sites:
            db.site.insert_many(new_sites)
            log_message(f"根域名 {root_domain_name} 插入了 {len(new_sites)} 个新的站点。")
        else:
            log_message(f"根域名 {root_domain_name} 没有新站点需要添加。")
        new_sites = []  # 清空列表,准备处理下一个根域名

def main():
    git_folder = "/ql/git_trickest_inventory"
    BBDB_MONGOURI = os.getenv("BBDB_MONGOURI")
    client = MongoClient(BBDB_MONGOURI)
    db = client.bbdb
    log_message("数据库连接成功")

    root_domain_names, blacklist_sub_domains, blacklist_urls, existing_sub_domains = load_db_data(db)
    domain_to_folder = {}

    # 遍历git_trickest_inventory文件夹，处理每个子文件夹中的hostnames.txt和servers.txt文件
    for root, dirs, files in os.walk(git_folder):
       if "hostnames.txt" in files:
           process_hostnames(os.path.join(root, "hostnames.txt"), domain_to_folder, root_domain_names)

    log_message(f"域名与文件夹的关联关系处理完毕，共有 {len(domain_to_folder)} 对关联关系")
    process_files_and_write_to_db(domain_to_folder, db, git_folder, root_domain_names, blacklist_sub_domains, blacklist_urls, existing_sub_domains)

    client.close()

if __name__ == "__main__":
    main()
