"""
文件名: bbdb_enscan.py
作者: soapffz
创建日期: 2024年3月20日
最后修改日期: 2024年3月20日
功能：使用enscan的api模式和client模式监测国内SRC主体关联公司资产变化
"""

import os
import requests
from pymongo import MongoClient
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta

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

def get_business_documents(db):
    """获取符合条件的business文档"""
    business_docs = list(db.business.find({"name": {"$regex": "^国内-"}}, {"company": 1, "name": 1}))
    log_message(f"找到符合条件的business文档数量: {len(business_docs)}")
    return business_docs

def send_requests(business_docs):
    """将business信息发送到ENSCANGO_API_URL"""
    ENSCANGO_API_URL = os.getenv("ENSCANGO_API_URL")
    for doc in business_docs:
        if "company" in doc:
            # 统一处理company字段为列表的情况
            company_names = doc["company"]
            if isinstance(company_names, str):
                company_names = [name.strip() for name in company_names.split(",") if name.strip()]
            elif isinstance(company_names, list):
                # 确保列表中的每个元素都是字符串，并去除空白字符
                company_names = [str(name).strip() for name in company_names if str(name).strip()]
            else:
                log_message(f"文档 {doc['name']} 的 company 字段类型未知", is_positive=False)
                continue

            for company_name in company_names:
                params = {
                    "orgname": company_name,
                    "invest": 100,
                    "branch": "true"
                }
                url = f"{ENSCANGO_API_URL}/api/info?{urlencode(params)}"
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        response_data = response.json()
                        # 检查是否触发了缓存逻辑
                        if response_data.get('code') == 0 and '入库' in response_data.get('message', ''):
                            log_message(f"{company_name} 已于 {response_data.get('inTime')} 入库队列查询")
                        else:
                            log_message(f"成功发送请求: {company_name}")
                            log_message(response.text)
                    else:
                        log_message(f"请求失败: {company_name}，状态码：{response.status_code}", is_positive=False)
                except Exception as e:
                    log_message(f"请求过程中遇到异常: {e}", is_positive=False)
        else:
            log_message(f"文档 {doc['name']} 没有 company 字段", is_positive=False)


def main():
    db = connect_to_db()
    business_docs = get_business_documents(db)
    send_requests(business_docs)

if __name__ == "__main__":
    main()
