"""
文件名: bbdb_empty_icp.py
作者: soapffz
创建日期: 2024年3月20日
最后修改日期: 2024年3月20日
功能：将备案信息为空的根域名尝试查询并添加，建议运行时间长一点，比如1天一次
"""

import os
from pymongo import MongoClient,UpdateOne
from datetime import datetime, timezone, timedelta
import requests
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

def connect_to_db():
    """连接到MongoDB数据库"""
    BBDB_MONGOURI = os.getenv("BBDB_MONGOURI")
    client = MongoClient(BBDB_MONGOURI)
    db = client.bbdb
    log_message("数据库连接成功")
    return db

def get_business_ids(db):
    """获取符合条件的business的_id"""
    business_ids = [str(doc['_id']) for doc in db.business.find({"name": {"$regex": "^国内-"}}, {"_id": 1})]
    log_message(f"国内 business 数量: {len(business_ids)}")
    return business_ids

def get_noicp_root_domains(db, business_ids):
    """查询符合条件的root_domain文档"""
    root_domains = list(db.root_domain.find({"business_id": {"$in": business_ids}, "$or": [{"company": {"$exists": False}}, {"company": ""}]}, {"_id": 1, "name": 1, "business_id": 1}))
    log_message(f"未查询备案的 root_domain 数量: {len(root_domains)}")
    return root_domains


def get_icp_info_by_mxnzp_com(domain):
    """从原有接口获取域名备案信息，并返回统一格式的字典"""
    app_id = os.getenv('MXNZP_COM_APP_ID')
    app_secret = os.getenv('MXNZP_COM_APP_SECRET')
    
    domain_encoded = base64.b64encode(domain.encode()).decode()
    url = f"https://www.mxnzp.com/api/beian/search?domain={domain_encoded}&app_id={app_id}&app_secret={app_secret}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 1:
                return {
                    'unit': data['data'].get('unit', ''),  # 主办单位名称
                    'type': data['data'].get('type', ''),  # 单位性质
                    'icpCode': data['data'].get('icpCode', ''),  # ICP备案号
                }
            else:
                log_message(f"Error: {data['msg']}", is_positive=False)
                return None
        else:
            log_message("HTTP Request failed", is_positive=False)
            return None
    except Exception as e:
        log_message(f"请求过程中遇到异常: {e}", is_positive=False)
        return None

def get_icp_info_by_muxiuge_com(domain):
    """通过木朽阁接口获取域名备案信息"""
    url = f"https://api.muxiuge.com/api/beian/?domain={domain}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                result = data['result']
                return {
                    'unit': result['name'],  # 主办单位名称
                    'type': result['nature'],  # 单位性质
                    'icpCode': result['icp'],  # ICP备案号
                }
            else:
                # 处理域名未备案的情况
                if data.get('errorCode') == 'error' and '未备案' in data.get('errorReason', ''):
                    # log_message(f"{domain} 未备案", is_positive=False)
                    return {'unit': '', 'type': '', 'icpCode': ''}
                else:
                    log_message(f"Error: {data.get('errorReason', 'Unknown error')}", is_positive=False)
                return None
        else:
            log_message("HTTP Request failed", is_positive=False)
            return None
    except Exception as e:
        log_message(f"请求过程中遇到异常: {e}", is_positive=False)
        return None

def get_icp_info_concurrently(domain_list):
    """并发获取多个域名的ICP信息"""
    results = {}
    with ThreadPoolExecutor(max_workers=16) as executor:  # 根据你的需求调整max_workers的值
        future_to_domain = {executor.submit(get_icp_info_by_muxiuge_com, domain): domain for domain in domain_list}
        for future in as_completed(future_to_domain):
            domain = future_to_domain[future]
            try:
                data = future.result()
                if data:  # 确保返回的数据不是None
                    results[domain] = data
            except Exception as exc:
                log_message(f"{domain} 生成异常: {exc}", is_positive=False)
    return results


def update_noicp_records(db, root_domains):
    """批量更新root_domain和business表，适应新的ICP信息获取方式"""
    domain_list = [rd['name'] for rd in root_domains]
    icp_info_results = get_icp_info_concurrently(domain_list)
    update_count = 0

    root_domain_updates = []  # 定义用于批量更新root_domain的操作列表
    business_updates = []  # 定义用于批量更新business的操作列表

    for rd in root_domains:
        domain_name = rd['name']
        if domain_name in icp_info_results:
            icp_info = icp_info_results[domain_name]
            # 检查unit是否为空
            if not icp_info['unit']:  # 如果unit为空，则跳过
                continue
            try:
                # 准备更新root_domain表的操作
                root_domain_update = UpdateOne({"_id": rd['_id']}, {"$set": {"company": icp_info['unit'], "icpregnum": icp_info['icpCode'], "company_type": icp_info['type']}})
                root_domain_updates.append(root_domain_update)

                # 查询并准备更新business表的操作
                business_doc = db.business.find_one({"_id": rd['business_id']})
                if business_doc and icp_info['unit'] not in business_doc.get('company', []):
                    business_update = UpdateOne({"_id": rd['business_id']}, {"$addToSet": {"company": icp_info['unit']}})
                    business_updates.append(business_update)

                update_count += 1
            except Exception as e:
                log_message(f"更新过程中遇到异常: {e}", is_positive=False)

    # 执行批量更新操作
    if root_domain_updates:
        db.root_domain.bulk_write(root_domain_updates)
    if business_updates:
        db.business.bulk_write(business_updates)
    
    if update_count > 0:
        log_message(f"未查询备案的 root_domain 成功更新个数: {update_count}")
    else:
        log_message(f"未查询备案的 root_domain 均未备案")

def main():
    db = connect_to_db()
    business_ids = get_business_ids(db)
    root_domains = get_noicp_root_domains(db, business_ids)
    update_noicp_records(db, root_domains)

if __name__ == "__main__":
    main()
