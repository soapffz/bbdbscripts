"""
new Env('bbdb备份到七牛');
50 23 * * * https://raw.githubusercontent.com/soapffz/bbdbscripts/main/bbdb_backup_to_qiniu.py

作者: soapffz
创建时间: 2024年3月18日
最后更新时间: 2024年3月18日
描述: 定时每晚23点50执行一次bbdb数据库备份到七牛云，并删除超过10份的较老备份。需apk add --no-cache mongodb-tools
"""


import os
import subprocess
import datetime
from qiniu import Auth, put_file, BucketManager
import re

def log(message, is_positive=True):
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')} {prefix} {message}")

def backup_bbdb_to_qiniu():
    qiniu_ak = os.getenv("QINIU_AK")
    qiniu_sk = os.getenv("QINIU_SK")
    mongodb_uri = os.getenv("BBDB_MONGOURI")
    bucket_name = os.getenv("BBDB_QINIU_BUCKET_NAME")
    backup_dir = os.getenv("BBDB_QINIU_BACKUP_DIR")

    backup_filename = f"bbdbbackup-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.gz"
    backup_filepath = f"/tmp/{backup_filename}"
    key = f"{backup_dir}/{backup_filename}"

    try:
        log("开始备份数据库...")
        result = subprocess.run(
            ["mongodump", "--uri", mongodb_uri, "--gzip", "--archive=" + backup_filepath, "--numParallelCollections=4"],
            capture_output=True, text=True)
        # 使用正则表达式匹配文档数量和表名
        pattern = re.compile(r"done dumping (\w+\.\w+) \((\d+) documents\)")
        for line in result.stderr.splitlines():
            match = pattern.search(line)
            if match:
                collection_name, documents_count = match.groups()
                log(f"{collection_name}: {documents_count}")
        log("数据库备份完成。")
    except subprocess.CalledProcessError as e:
        log(f"备份数据库时发生错误: {e}", False)
        return

    q = Auth(qiniu_ak, qiniu_sk)
    token = q.upload_token(bucket_name, key, 3600)

    try:
        log("开始上传备份文件到七牛云...")
        put_file(token, key, backup_filepath)
        log("上传完成。")
    except Exception as e:
        log(f"上传到七牛云时发生错误: {e}", False)
        return

    # 保留云端最新的10份备份，删除其他
    bucket_manager = BucketManager(q)
    prefix = backup_dir + "/"
    ret, eof, info = bucket_manager.list(bucket_name, prefix=prefix, limit=1000)
    if ret is not None:
        items = sorted(ret['items'], key=lambda x: x['putTime'], reverse=True)
        for item in items[10:]:
            bucket_manager.delete(bucket_name, item['key'])
            log(f"删除旧备份文件：{item['key']}")

    try:
        os.remove(backup_filepath)
        log("本地备份文件已清理。")
    except Exception as e:
        log(f"清理本地备份文件时发生错误: {e}", False)

if __name__ == "__main__":
    backup_bbdb_to_qiniu()
