"""
new Env('更新推送给AWVS的URL');
* * * * * https://raw.githubusercontent.com/soapffz/bbdbscripts/main/bbdb_update_site_to_awvs.py

文件名: bbdb_update_site_to_awvs.py
作者: soapffz
创建日期: 2024年3月27日
最后修改日期: 2024年3月27日

定时执行，根据test502git/awvs14-scan脚本输出判断AWVS扫描中数量，补齐固定数量的url去扫描
"""

from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import subprocess
import re
from subprocess import Popen, PIPE, TimeoutExpired


def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(
        f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}"
    )


# MongoDB连接信息
mongo_uri = "mongodb://192.168.2.188:27017/"
db_name = "bbdb"  # 替换为实际的数据库名称
collection_name = "site"  # 替换为实际的集合名称

# 文件路径
url_file_path = "/ql/awvs14-scan/url.txt"
progress_file_path = "./progress_of_push_to_awvs.txt"

# 连接到MongoDB
client = MongoClient(mongo_uri)
db = client[db_name]
collection = db[collection_name]
log_message("数据库连接成功")


def get_scan_status():
    """获取当前扫描状态，如果脚本一直等待输出，则在超时后强行终止"""
    try:
        # 启动脚本并等待指定的超时时间
        with Popen(
            ["python3", "awvs14_script.py"],
            stdout=PIPE,
            stderr=PIPE,
            text=True,
            cwd="/ql/awvs14-scan/",
        ) as process:
            try:
                stdout, stderr = process.communicate(timeout=1)  # 设置超时时间
            except TimeoutExpired:
                process.kill()  # 超时后杀死进程
                stdout, stderr = process.communicate()  # 获取进程的输出

        # 解析输出以获取当前扫描中的URL数量
        match = re.search(r"扫描中: (\d+)", stdout)
        if match:
            return int(match.group(1))
    except Exception as e:
        print(f"获取扫描状态时发生错误: {e}")
    return 0


def update_url_file(urls):
    """更新url.txt文件内容"""
    with open(url_file_path, "w") as file:
        file.writelines("\n".join(urls) + "\n")


def get_processed_ids():
    """获取已处理的site的_id，如果文件不存在则创建"""
    try:
        with open(progress_file_path, "r") as file:
            return file.read().splitlines()
    except FileNotFoundError:
        # 文件不存在时创建文件
        open(progress_file_path, "w").close()
        return []


def add_processed_id(site_id):
    """将处理过的site的_id添加到进度文件中，如果文件不存在则创建"""
    with open(progress_file_path, "a") as file:
        file.write(f"{site_id}\n")


def get_all_sites():
    """从数据库中加载所有site数据到内存"""
    return list(collection.find({}))


def get_new_urls(needed_count, all_sites):
    """从内存中的数据筛选指定数量的新URL进行扫描"""
    processed_ids = get_processed_ids()
    filtered_sites = [
        site for site in all_sites if str(site["_id"]) not in processed_ids
    ]
    sorted_sites = sorted(filtered_sites, key=lambda x: x["create_time"])[:needed_count]
    urls = [site["name"] for site in sorted_sites]
    return urls, [str(site["_id"]) for site in sorted_sites]


def main():
    all_sites = get_all_sites()  # 加载所有site数据到内存
    current_scanning = get_scan_status()
    log_message(f"当前扫描中的URL数量: {current_scanning}")
    if current_scanning < 10:
        needed_count = 10 - current_scanning
        log_message(f"需要添加 {needed_count} 条URL")
        new_urls, new_ids = get_new_urls(needed_count, all_sites)
        if new_urls:
            update_url_file(new_urls)
            for site_id in new_ids:
                add_processed_id(site_id)
            log_message("添加的URLs:")
            for url in new_urls:
                log_message(url)
            # 在这里调用awvs14_script.py进行扫描，屏蔽输出
            subprocess.run(
                ["python3", "awvs14_script.py"],
                input="1\n1\narl\n".encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd="/ql/awvs14-scan/",
            )
            log_message("已更新URL并启动扫描")
        else:
            log_message("没有更多新的URL可供添加", is_positive=False)
    else:
        log_message("当前扫描中的URL数量已经达到或超过了10条", is_positive=False)


if __name__ == "__main__":
    main()
