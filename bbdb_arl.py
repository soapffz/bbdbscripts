"""
new Env('bbdb-ARL联动');
*/10 * * * * https://raw.githubusercontent.com/soapffz/bbdbscripts//main/bbdb_arl.py

本脚本实现了bbdb和ARL之间的联动，主要包括以下步骤：

1. 从bbdb全量读取"国内-"开头的business，root_domain,sub_domain数据，并登录ARL获取token。
2. 获取ARL中资产分组的名称，并与business中的name进行比较，确定需要互相插入的资产分组。
3. 首先进行bbdb向ARL进行新分组的插入，插入根域名和子域名（合并去重，保持原有顺序，根域名在先），scope_type为domain。
4. 完成后，再进行ARL向bbdb的插入。对于每一个只在 ARL 资产分组中的 name，添加到 bbdb 中。
5. 扫描策略配置。为ARL中没有对应扫描策略的资产分组，添加与其资产分组名称相同的扫描策略.
6. 域名资产同步。对双向相同的分组中的域名资产进行双向同步，bbdb侧从内存中读取比较后，提取绝对根域名并对比root_domain表，子域名对比sub_domain表，ARL侧则将新增子域名直接插入资产分组的资产范围中后，将新增的域名也启动监控任务。
7. IP资产同步。对双向相同的分组中的IP资产进行双向同步，bbdb侧从内存中读取比较后，提取IP并对比ip表，ARL侧则将新增IP直接插入资产分组的资产范围中后，将新增的IP也启动监控任务。
8. 监控任务触发。配置好资产分组和对应的策略后，批量为新增的策略和资产分组触发监控和站点监控任务。
9. 在每次脚本运行结束后，统计双方互相同步的新资产分组数量，新同步的子域名数量、IP数量。

"""

from pymongo import MongoClient
import requests
import json
import sys
import urllib3
import re
from datetime import datetime
import requests
import json
import logging
import yaml

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

urllib3.disable_warnings()


def check_env_vars(config):
    # 定义所有需要的环境变量
    required_env_vars = [
        "BBDB_ARL_URL",
        "BBDB_ARL_USERNAME",
        "BBDB_ARL_PASSWORD",
        "BBDB_MONGODB_URI",
    ]

    # 检查每个环境变量
    for var in required_env_vars:
        if not config["DEFAULT"].get(var):
            print(f"环境变量 {var} 无效。请检查你的环境变量设置。")
            return False

    # 如果所有环境变量都有效，返回 True
    return True


# 登录ARL
def login_arl(arl_url, username, password):
    if not all([arl_url, username, password]):
        logging.error("ARL URL, username or password is missing.")
        return None

    data = {"username": username, "password": password}
    headers = {"Content-Type": "application/json; charset=UTF-8"}

    try:
        response = requests.post(
            arl_url + "/api/user/login", headers=headers, json=data, verify=False
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        return None

    try:
        response_data = response.json()
    except ValueError:
        logging.error("Failed to decode JSON response.")
        return None

    if response_data.get("code") != 200:
        logging.error(f"ARL login failed, error code: {response_data.get('code')}")
        return None

    token = response_data.get("data", {}).get("token")
    if not token:
        logging.error("Token is missing in the response.")
        return None

    print("ARL login successful.")
    return token


def get_bbdb_data(db):
    # 从数据库中获取所有的数据
    all_businesses = list(db["business"].find())
    all_root_domains = list(db["root_domain"].find())
    all_sub_domains = list(db["sub_domain"].find())

    # 在内存中过滤出以 "国内-" 开头的数据
    businesses = [
        business for business in all_businesses if business["name"].startswith("国内-")
    ]

    # 根据business_id筛选对应的root_domain和sub_domain
    business_ids = [business["_id"] for business in businesses]
    root_domains = [
        domain for domain in all_root_domains if domain["business_id"] in business_ids
    ]
    sub_domains = [
        domain for domain in all_sub_domains if domain["business_id"] in business_ids
    ]

    return businesses, root_domains, sub_domains


def compare_business_and_arl(businesses, arl_all_asset_scopes):
    arl_names = [asset_scope["name"] for asset_scope in arl_all_asset_scopes]
    business_names = [business["name"] for business in businesses]
    business_only_asset_scopes = set(business_names).difference(arl_names)
    arl_only_asset_scopes = set(arl_names).difference(business_names)
    return business_only_asset_scopes, arl_only_asset_scopes


def insert_new_group_to_arl(
    token, arl_url, business_only_asset_scopes, businesses, root_domains, sub_domains
):
    # 获取所有的资产分组名称
    arl_asset_scope_names = fetch_arl_asset_scope_names(token, arl_url)

    for business_name in business_only_asset_scopes:
        # 检查资产分组是否已经存在
        if business_name in arl_asset_scope_names:
            # print(f"资产分组 {business_name} 已经存在，跳过插入")
            continue
        # 获取对应的 business_id
        business_id = next(
            (
                business["_id"]
                for business in businesses
                if business["name"] == business_name
            ),
            None,
        )
        if not business_id:
            print(f"无法找到业务 {business_name} 的 ID")
            continue

        # 获取对应的根域名和子域名
        rootdomain_names = [
            domain["name"]
            for domain in root_domains
            if domain["business_id"] == business_id
        ]
        subdomain_names = [
            domain["name"]
            for domain in sub_domains
            if domain["business_id"] == business_id
        ]

        # 合并去重，保持原有顺序，根域名在先
        all_domains = rootdomain_names + subdomain_names
        if all_domains:
            scope = ",".join(list(set(all_domains)))
            # 添加到 ARL 资产分组中
            add_asset_scope(token, arl_url, business_name, scope)
        else:
            continue


def add_asset_scope(token, arl_url, name, scope):
    # 获取所有的资产分组名称
    arl_asset_scope_names = fetch_arl_asset_scope_names(token, arl_url)

    # 检查资产分组是否已经存在
    if name in arl_asset_scope_names:
        # print(f"资产分组 {name} 已经存在，跳过添加")
        return

    # 准备请求数据
    data = {"scope_type": "domain", "name": name, "scope": scope}
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}

    # 发送请求
    try:
        response = requests.post(
            arl_url + "/api/asset_scope/", headers=headers, json=data, verify=False
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(e, "出错了，请排查")
        return None

    # 解析响应内容
    try:
        response_data = response.json()
    except ValueError:
        print("无法解析" + name + "响应内容")
        return None

    if response_data:
        scope_id = response_data.get("data", {}).get("scope_id")
        if not scope_id:
            print("{name} 返回scope_id为空")
            exit(-1)
    else:
        print("无法解析" + name + "响应内容")


def fetch_arl_asset_scope_names(token, arl_url):
    asset_scopes = retrieve_all_arl_asset_scopes(token, arl_url)
    return set(asset_scope["name"] for asset_scope in asset_scopes)


def retrieve_all_arl_asset_scopes(token, arl_url):
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}
    size = 10
    all_asset_scopes = []
    page = 1
    total_pages = None  # 初始化总页数为 None

    while total_pages is None or page <= total_pages:
        try:
            response = requests.get(
                arl_url + f"/api/asset_scope/?size={size}&page={page}",
                headers=headers,
                verify=False,
            )
            response.raise_for_status()
            response_data = response.json()
        except requests.RequestException as e:
            logging.error(f"Request failed: {e}")
            break
        except ValueError:
            logging.error("Failed to decode JSON response.")
            break

        if total_pages is None:
            total = response_data.get("total", 0)
            total_pages = (total + size - 1) // size  # 计算总页数

        if "items" in response_data:
            all_asset_scopes.extend(response_data["items"])
        else:
            print("响应中没有 'items' 键")
            break

        page += 1  # 请求下一页

    return all_asset_scopes


def insert_new_group_to_bbdb(db, arl_only_asset_scopes, arl_all_asset_scopes):
    for arl_name in arl_only_asset_scopes:
        # 找到对应的资产分组
        asset_scope = next(
            (
                asset_scope
                for asset_scope in arl_all_asset_scopes
                if asset_scope["name"] == arl_name
            ),
            None,
        )
        if asset_scope is None:
            print(f"无法找到资产分组 {arl_name}")
            continue

        # 检查 business 是否已存在
        if db["business"].find_one({"name": arl_name}):
            continue

        # 创建 business
        business = {
            "name": arl_name,
            "notes": "from arl",
            "url": "",
            "create_time": datetime.now(),
            "update_time": datetime.now(),
        }
        business_id = db["business"].insert_one(business).inserted_id

        # 提取所有域名
        all_domains = asset_scope["scope_array"]

        # 提取每个域名的绝对根域名
        absolute_root_domains = []
        pattern = r"[\w-]+\.[\w-]+$"
        for domain in all_domains:
            match = re.search(pattern, domain)
            if match:
                root_domain = match.group()
                absolute_root_domains.append(root_domain)

        # 去重
        absolute_root_domains = list(set(absolute_root_domains))

        # 如果绝对根域名列表为空，则全部视为子域名
        if not absolute_root_domains:
            # 绑定business_id，插入sub_domain表
            sub_domains_to_insert = [
                {
                    "name": domain,
                    "icpregnum": "",
                    "business_id": business_id,
                    "notes": "from arl",
                    "create_time": datetime.now(),
                    "update_time": datetime.now(),
                }
                for domain in all_domains
                if not db["sub_domain"].find_one({"name": domain})
            ]
            if sub_domains_to_insert:
                db["sub_domain"].insert_many(sub_domains_to_insert)
        else:
            # 将原有读取的域名中的剩下的域名作为子域名
            remaining_domains = list(set(all_domains) - set(absolute_root_domains))

            # 插入根域名
            root_domains_to_insert = [
                {
                    "name": domain,
                    "icpregnum": "",
                    "business_id": business_id,
                    "notes": "from arl",
                    "create_time": datetime.now(),
                    "update_time": datetime.now(),
                }
                for domain in absolute_root_domains
                if not db["root_domain"].find_one({"name": domain})
            ]
            if root_domains_to_insert:
                root_domain_insert_result = db["root_domain"].insert_many(
                    root_domains_to_insert
                )
                root_domain_ids = root_domain_insert_result.inserted_ids

            # 插入子域名
            sub_domains_to_insert = []
            for domain in remaining_domains:
                # 获取对应的 root_domain_id
                root_domain_id = next(
                    (
                        _id
                        for _id, root_domain in zip(
                            root_domain_ids, absolute_root_domains
                        )
                        if root_domain == re.search(pattern, domain).group()
                    ),
                    None,
                )
                if root_domain_id is not None and not db["sub_domain"].find_one(
                    {"name": domain}
                ):
                    sub_domain_data = {
                        "name": domain,
                        "icpregnum": "",
                        "root_domain_id": root_domain_id,
                        "business_id": business_id,
                        "notes": "from arl",
                        "create_time": datetime.now(),
                        "update_time": datetime.now(),
                    }
                    sub_domains_to_insert.append(sub_domain_data)

            if sub_domains_to_insert:
                db["sub_domain"].insert_many(sub_domains_to_insert)


def add_policy(arl_url, token, policy_name, scope_id):
    # 获取所有的策略
    arl_all_policies = get_arl_all_policies(arl_url, token)
    # 检查策略是否已经存在
    if any(policy["name"] == policy_name for policy in arl_all_policies):
        print(f"策略 {policy_name} 已经存在，跳过添加")
        return

    # 准备请求参数
    payload = {
        "name": policy_name,
        "desc": "set by soapffz",
        "policy": {
            "domain_config": {
                "domain_brute": True,
                "alt_dns": True,
                "arl_search": True,
                "dns_query_plugin": True,
                "skip_scan_cdn_ip": True,
                "domain_brute_type": "big",
            },
            "ip_config": {
                "port_scan": True,
                "service_detection": False,
                "os_detection": False,
                "ssl_cert": False,
                "port_scan_type": "all",
                "port_custom": "",
                "host_timeout_type": "default",
                "host_timeout": 0,
                "port_parallelism": 32,
                "port_min_rate": 60,
            },
            "npoc_service_detection": False,
            "site_config": {
                "site_identify": False,
                "search_engines": False,
                "site_spider": False,
                "site_capture": False,
                "nuclei_scan": False,
            },
            "file_leak": True,
            "poc_config": [
                {
                    "plugin_name": "WEB_INF_WEB_xml_leak",
                    "vul_name": "WEB-INF/web.xml 文件泄漏",
                    "enable": True,
                },
                {
                    "plugin_name": "Ueditor_Store_XSS",
                    "vul_name": "Ueditor 存储 XSS 漏洞",
                    "enable": True,
                },
                {
                    "plugin_name": "Ueditor_SSRF",
                    "vul_name": "Ueditor SSRF 漏洞",
                    "enable": True,
                },
                {
                    "plugin_name": "Gitlab_Username_Leak",
                    "vul_name": "Gitlab 用户名泄漏",
                    "enable": True,
                },
                {
                    "plugin_name": "Django_Debug_Info",
                    "vul_name": "Django 开启调试模式",
                    "enable": True,
                },
                {
                    "plugin_name": "ZooKeeper_noauth",
                    "vul_name": "ZooKeeper 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Solr_noauth",
                    "vul_name": "Apache solr 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Redis_noauth",
                    "vul_name": "Redis 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Onlyoffice_noauth",
                    "vul_name": "Onlyoffice 未授权漏洞",
                    "enable": True,
                },
                {
                    "plugin_name": "Nacos_noauth",
                    "vul_name": "Nacos 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Mongodb_noauth",
                    "vul_name": "Mongodb 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Memcached_noauth",
                    "vul_name": "Memcached 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Kibana_noauth",
                    "vul_name": "Kibana 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Headless_remote_API_noauth",
                    "vul_name": "Headless Remote API 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Hadoop_YARN_RPC_noauth",
                    "vul_name": "Hadoop YARN RCP 未授权访问漏洞",
                    "enable": True,
                },
                {
                    "plugin_name": "Elasticsearch_noauth",
                    "vul_name": "Elasticsearch 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Druid_noauth",
                    "vul_name": "Druid 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "DockerRemoteAPI_noauth",
                    "vul_name": "Docker Remote API 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Apollo_Adminservice_noauth",
                    "vul_name": "apollo-adminservice 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Actuator_noauth_bypass_waf",
                    "vul_name": "Actuator API 未授权访问 (绕过WAF)",
                    "enable": True,
                },
                {
                    "plugin_name": "Actuator_noauth",
                    "vul_name": "Actuator API 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "Actuator_httptrace_noauth",
                    "vul_name": "Actuator httptrace API 未授权访问",
                    "enable": True,
                },
                {
                    "plugin_name": "vcenter_identify",
                    "vul_name": "VMware vCenter",
                    "enable": True,
                },
                {
                    "plugin_name": "XXL_Job_Admin_Identify",
                    "vul_name": "xxl-job-admin",
                    "enable": True,
                },
                {
                    "plugin_name": "Weaver_Ecology_Identify",
                    "vul_name": "Ecology",
                    "enable": True,
                },
                {
                    "plugin_name": "Swagger_Json_Identify",
                    "vul_name": "Swagger 文档接口",
                    "enable": True,
                },
                {
                    "plugin_name": "Shiro_Identify",
                    "vul_name": "Apache Shiro",
                    "enable": True,
                },
                {
                    "plugin_name": "Oracle_Weblogic_Console_Identify",
                    "vul_name": "Oracle Weblogic 控制台",
                    "enable": True,
                },
                {"plugin_name": "Nacos_Identify", "vul_name": "Nacos", "enable": True},
                {
                    "plugin_name": "Hystrix_Dashboard_Identify",
                    "vul_name": "Hystrix Dashboard",
                    "enable": True,
                },
                {
                    "plugin_name": "Harbor_Identify",
                    "vul_name": "Harbor API",
                    "enable": True,
                },
                {
                    "plugin_name": "Graphql_Identify",
                    "vul_name": "Graphql 接口",
                    "enable": True,
                },
                {
                    "plugin_name": "Grafana_Identify",
                    "vul_name": "Grafana",
                    "enable": True,
                },
                {
                    "plugin_name": "Finereport_Identify",
                    "vul_name": "帆软 FineReport",
                    "enable": True,
                },
                {
                    "plugin_name": "FinereportV10_Identify",
                    "vul_name": "帆软 FineReport V10",
                    "enable": True,
                },
                {
                    "plugin_name": "Clickhouse_REST_API_Identify",
                    "vul_name": "Clickhouse REST API",
                    "enable": True,
                },
                {
                    "plugin_name": "Apache_Ofbiz_Identify",
                    "vul_name": "Apache Ofbiz",
                    "enable": True,
                },
                {
                    "plugin_name": "Apache_Apereo_CAS_Identify",
                    "vul_name": "Apache Apereo Cas",
                    "enable": True,
                },
                {
                    "plugin_name": "Any800_Identify",
                    "vul_name": "Any800全渠道智能客服云平台",
                    "enable": True,
                },
                {
                    "plugin_name": "Adminer_PHP_Identify",
                    "vul_name": "Adminer.php",
                    "enable": True,
                },
            ],
            "brute_config": [
                {
                    "plugin_name": "TomcatBrute",
                    "vul_name": "Tomcat 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "Shiro_GCM_Brute",
                    "vul_name": "Shiro GCM 弱密钥",
                    "enable": True,
                },
                {
                    "plugin_name": "Shiro_CBC_Brute",
                    "vul_name": "Shiro CBC 弱密钥",
                    "enable": True,
                },
                {"plugin_name": "SSHBrute", "vul_name": "SSH 弱口令", "enable": True},
                {
                    "plugin_name": "SQLServerBrute",
                    "vul_name": "SQLServer 弱口令",
                    "enable": True,
                },
                {"plugin_name": "SMTPBrute", "vul_name": "SMTP 弱口令", "enable": True},
                {"plugin_name": "RedisBrute", "vul_name": "Redis 弱口令", "enable": True},
                {"plugin_name": "RDPBrute", "vul_name": "RDP 弱口令", "enable": True},
                {
                    "plugin_name": "PostgreSQLBrute",
                    "vul_name": "PostgreSQL 弱口令",
                    "enable": True,
                },
                {"plugin_name": "POP3Brute", "vul_name": "POP3 弱口令", "enable": True},
                {
                    "plugin_name": "OpenfireBrute",
                    "vul_name": "Openfire 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "NexusBrute",
                    "vul_name": "Nexus Repository 弱口令",
                    "enable": True,
                },
                {"plugin_name": "NacosBrute", "vul_name": "Nacos 弱口令", "enable": True},
                {"plugin_name": "MysqlBrute", "vul_name": "MySQL 弱口令", "enable": True},
                {
                    "plugin_name": "MongoDBBrute",
                    "vul_name": "MongoDB 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "JenkinsBrute",
                    "vul_name": "Jenkins 弱口令",
                    "enable": True,
                },
                {"plugin_name": "IMAPBrute", "vul_name": "IMAP 弱口令", "enable": True},
                {
                    "plugin_name": "HarborBrute",
                    "vul_name": "Harbor 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "GrafanaBrute",
                    "vul_name": "Grafana 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "GitlabBrute",
                    "vul_name": "Gitlab 弱口令",
                    "enable": True,
                },
                {"plugin_name": "FTPBrute", "vul_name": "FTP 弱口令", "enable": True},
                {
                    "plugin_name": "ExchangeBrute",
                    "vul_name": "Exchange 邮件服务器弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "CobaltStrikeBrute",
                    "vul_name": "CobaltStrike 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "ClickhouseBrute",
                    "vul_name": "Clickhouse 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "AlibabaDruidBrute",
                    "vul_name": "Alibaba Druid 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "ActiveMQBrute",
                    "vul_name": "ActiveMQ 弱口令",
                    "enable": True,
                },
                {
                    "plugin_name": "APISIXBrute",
                    "vul_name": "APISIX 弱口令",
                    "enable": True,
                },
            ],
            "scope_config": {"scope_id": scope_id},
        },
    }

    # 准备请求参数
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}

    # 发送请求
    try:
        response = requests.post(
            arl_url + "/api/policy/add/", headers=headers, json=payload, verify=False
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(e, "出错了，请排查")
        return None

    # 检查响应是否有效
    try:
        response_data = response.json()
    except ValueError:
        print(f"无法解析ADD {policy_name} 策略的响应内容")
        return None

    policy_id = response_data.get("data", {}).get("policy_id")
    # 返回策略ID
    return policy_id


def get_arl_all_policies(arl_url, token):
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}
    size = 10
    all_policies = []
    page = 1
    total_pages = None  # 初始化总页数为 None

    while total_pages is None or page <= total_pages:
        try:
            response = requests.get(
                arl_url + f"/api/policy/?size={size}&page={page}",
                headers=headers,
                verify=False,
            )
            response.raise_for_status()
            response_data = response.json()
        except requests.RequestException as e:
            print(e, "出错了，请排查")
            break
        except ValueError:
            print("无法解析响应内容")
            break

        if total_pages is None:
            total = response_data.get("total", 0)
            total_pages = (total + size - 1) // size  # 计算总页数

        if "items" in response_data:
            all_policies.extend(response_data["items"])
        else:
            print("响应中没有 'items' 键")
            break

        page += 1  # 请求下一页

    return all_policies


def get_unconfigured_asset_group_ids(arl_url, token, arl_scope_ids):
    # 获取所有的策略
    arl_all_policies = get_arl_all_policies(arl_url, token)

    # 从策略中提取所有的 scope_id
    policy_scope_ids = [
        policy["policy"]["scope_config"]["scope_id"]
        for policy in arl_all_policies
        if "scope_config" in policy["policy"]
        and "scope_id" in policy["policy"]["scope_config"]
    ]

    # 找出没有配置策略的资产组
    unconfigured_asset_group_ids = list(set(arl_scope_ids) - set(policy_scope_ids))

    return unconfigured_asset_group_ids


def add_scheduler(token, arl_url, scope_id, domain, policy_id):
    # 准备请求数据
    data = {
        "scope_id": scope_id,
        "domain": domain,
        "interval": 86400,
        "policy_id": policy_id,
        "name": "",
    }
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}

    # 发送请求
    try:
        response = requests.post(
            arl_url + "/api/scheduler/add/", headers=headers, json=data, verify=False
        )
        response.raise_for_status()
    except requests.RequestException as e:
        return


def check_scheduler_exists(token, arl_url, domain):
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}
    try:
        response = requests.get(
            arl_url + f"/api/scheduler/?domain={domain}", headers=headers, verify=False
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(e, "出错了，请排查")
        return False

    response_data = response.json()
    if response_data and response_data.get("total", 0) > 0:
        return True
    else:
        return False


def add_site_monitor(token, arl_url, scope_id):
    # 准备请求数据
    data = {
        "scope_id": scope_id,
        "interval": 86400,
    }
    headers = {"Token": token, "Content-Type": "application/json; charset=UTF-8"}

    # 发送请求
    try:
        response = requests.post(
            arl_url + "/api/scheduler/add/site_monitor/",
            headers=headers,
            json=data,
            verify=False,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(e, "出错了，请排查")


def sync_domain_assets(
    db,
    token,
    arl_url,
    businesses,
    root_domains,
    sub_domains,
    arl_all_asset_scopes,
    arl_all_policies,
):
    global new_domains_to_arl, new_domains_to_bbdb
    for asset_scope in arl_all_asset_scopes:
        scope_id = asset_scope["_id"]
        arl_domains = set(asset_scope["scope_array"])

        # 从bbdb获取对应的域名
        business_id = next(
            (
                business["_id"]
                for business in businesses
                if business["name"] == asset_scope["name"]
            ),
            None,
        )
        if business_id is None:
            continue
        bbdb_domains = set(
            domain["name"]
            for domain in root_domains
            if domain["business_id"] == business_id
        )
        bbdb_domains.update(
            domain["name"]
            for domain in sub_domains
            if domain["business_id"] == business_id
        )

        # 找出需要添加到ARL的域名
        new_domains_to_arl = bbdb_domains - arl_domains
        if new_domains_to_arl:
            # 添加到ARL的资产分组中
            data = {
                "scope_id": scope_id,
                "scope": ",".join(new_domains_to_arl),
            }
            headers = {
                "Token": token,
                "Content-Type": "application/json; charset=UTF-8",
            }
            try:
                response = requests.post(
                    arl_url + "/api/asset_scope/add/",
                    headers=headers,
                    json=data,
                    verify=False,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                print(e, "出错了，请排查")
            if response.status_code == 200:
                print(
                    f"Added {len(new_domains_to_arl)} domains to ARL asset scope {scope_id}"
                )
            else:
                print(f"Failed to add domains to ARL asset scope {scope_id}")

            # 找到对应的策略
            policy = next(
                (
                    policy
                    for policy in arl_all_policies
                    if policy["policy"]["scope_config"]["scope_id"] == scope_id
                ),
                None,
            )
            if policy is not None:
                policy_id = policy["_id"]
                # 触发监控任务
                for domain in new_domains_to_arl:
                    add_scheduler(token, arl_url, scope_id, domain, policy_id)

        # 找出需要添加到bbdb的域名
        new_domains_to_bbdb = arl_domains - bbdb_domains
        if new_domains_to_bbdb:
            # 添加到bbdb的root_domain和sub_domain表中
            root_domains_to_add = [
                {"business_id": business_id, "domain": domain}
                for domain in new_domains_to_bbdb
                if domain in root_domains
            ]
            sub_domains_to_add = [
                {"business_id": business_id, "domain": domain}
                for domain in new_domains_to_bbdb
                if domain not in root_domains
            ]

            if root_domains_to_add:
                db["root_domains"].insert_many(root_domains_to_add)
            if sub_domains_to_add:
                db["sub_domains"].insert_many(sub_domains_to_add)


def sync_ip_assets(db, arl_all_asset_scopes, businesses):
    global new_ips_to_bbdb
    for asset_scope in arl_all_asset_scopes:
        scope_id = asset_scope["_id"]
        items = asset_scope["items"] if "items" in asset_scope else [asset_scope]
        arl_ips = set(
            item["record"][0]
            for item in items
            if "type" in item
            and item["type"] == "A"
            and "record" in item
            and item["record"]
        )
        # 从bbdb获取对应的IP
        business_id = next(
            (
                business["_id"]
                for business in businesses
                if business["name"] == asset_scope["name"]
            ),
            None,
        )
        if business_id is None:
            continue
        bbdb_ips = set(ip["ip"] for ip in db["ip"].find({"business_id": business_id}))

        # 找出需要添加到bbdb的IP
        new_ips_to_bbdb = arl_ips - bbdb_ips
        if new_ips_to_bbdb:
            # 添加到bbdb的ip表中
            db["ip"].insert_many(
                [
                    {
                        "ip": ip,
                        "business_id": business_id,
                        "notes": "from arl",
                        "create_time": datetime.now(),
                        "update_time": datetime.now(),
                    }
                    for ip in new_ips_to_bbdb
                ]
            )
            print(f"Added {len(new_ips_to_bbdb)} IPs to bbdb business {business_id}")


def main():
    # 读取配置文件
    with open("config_debug.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 检查环境变量
    if not check_env_vars(config):
        sys.exit("环境变量检查失败。")

    # 从配置文件读取环境变量
    arl_url = config["DEFAULT"].get("BBDB_ARL_URL")
    username = config["DEFAULT"].get("BBDB_ARL_USERNAME")
    password = config["DEFAULT"].get("BBDB_ARL_PASSWORD")
    mongodb_uri = config["DEFAULT"].get("BBDB_MONGODB_URI")

    # 连接到MongoDB
    client = MongoClient(mongodb_uri)
    db = client["bbdb"]

    global new_domains_to_arl, new_domains_to_bbdb, new_ips_to_bbdb
    new_domains_to_arl = set()
    new_domains_to_bbdb = set()
    new_ips_to_bbdb = set()

    # 1. 从bbdb全量读取"国内-"开头的business，root_domain,sub_domain数据，并登录ARL获取token。
    token = login_arl(arl_url, username, password)
    print("1-bbdb读取中..")
    businesses, root_domains, sub_domains = get_bbdb_data(db)
    print("1-读取bbdb完成，准备获取arl资产分组")

    # 2. 获取ARL中资产分组的名称，并与business中的name进行比较，确定需要互相插入的资产分组。
    arl_all_asset_scopes = retrieve_all_arl_asset_scopes(token, arl_url)
    business_only_asset_scopes, arl_only_asset_scopes = compare_business_and_arl(
        businesses, arl_all_asset_scopes
    )
    arl_scope_ids = [asset_scope["_id"] for asset_scope in arl_all_asset_scopes]
    print("2-arl和bbdb分组信息确认完成，准备arl插入")

    # 3. 首先进行bbdb向ARL进行新分组的插入，插入根域名和子域名（合并去重，保持原有顺序，根域名在先），scope_type为domain。
    insert_new_group_to_arl(
        token,
        arl_url,
        business_only_asset_scopes,
        businesses,
        root_domains,
        sub_domains,
    )
    print("3-arl分组插入完成")

    # 重新获取ARL中资产分组的scope_id
    arl_all_asset_scopes = retrieve_all_arl_asset_scopes(token, arl_url)
    print("3-刷新arl分组资产..")

    # 4. 完成后，再进行ARL向bbdb的插入。对于每一个只在 ARL 资产分组中的 name，添加到 bbdb 中
    insert_new_group_to_bbdb(db, arl_only_asset_scopes, arl_all_asset_scopes)
    print("4-bbdb分组插入完成，等待检测分组扫描策略是否完整..")

    # 5.扫描策略配置。为ARL中没有对应扫描策略的资产分组，添加与其资产分组名称相同的扫描策略.
    arl_all_policies = get_arl_all_policies(arl_url, token)
    unconfigured_asset_groups = get_unconfigured_asset_group_ids(
        arl_url, token, arl_scope_ids
    )
    for scope_id in unconfigured_asset_groups:
        # 找到对应的资产分组名称
        asset_group_name = next(
            (
                asset_scope["name"]
                for asset_scope in arl_all_asset_scopes
                if asset_scope["_id"] == scope_id
            ),
            None,
        )
        if asset_group_name is not None:
            try:
                add_policy(arl_url, token, asset_group_name, scope_id)
            except Exception as e:
                print(f"Failed to add policy for asset group {asset_group_name}: {e}")
        else:
            print(f"Asset group with scope_id {scope_id} not found")
    print("5-策略检测完成")

    # 重新获取bbdb的root_domains和sub_domains
    print("5-等待刷新bbdb..")
    businesses, root_domains, sub_domains = get_bbdb_data(db)
    print("5-刷新bbdb完成，开始双向域名资产同步..")

    # 6. 域名资产同步。对双向相同的分组中的域名资产进行双向同步，bbdb侧从内存中读取比较后，提取绝对根域名并对比root_domain表，子域名对比sub_domain表，ARL侧则将新增子域名直接插入资产分组的资产范围中后，将新增的域名也启动监控任务。
    sync_domain_assets(
        db,
        token,
        arl_url,
        businesses,
        root_domains,
        sub_domains,
        arl_all_asset_scopes,
        arl_all_policies,
    )
    print("6-域名资产双向同步完成")

    # 重新获取bbdb的root_domains和sub_domains
    print("6-等待刷新bbdb..")
    businesses, root_domains, sub_domains = get_bbdb_data(db)
    print("6-刷新bbdb完成")

    # 7. IP资产同步。对双向相同的分组中的IP资产进行双向同步，bbdb侧从内存中读取比较后，提取IP并对比ip表，ARL侧则将新增IP直接插入资产分组的资产范围中后，将新增的IP也启动监控任务。
    sync_ip_assets(db, arl_all_asset_scopes, businesses)
    print("7-ip资产导入bbdb完成,开始添加arl监控任务..")

    # 8.监控任务触发。配置好资产分组和对应的策略后，批量为新增的策略和资产分组触发监控和站点监控任务。
    print("8-刷新arl资产，准备批量添加监控任务.")
    # 重新获取策略列表
    arl_all_policies = get_arl_all_policies(arl_url, token)
    arl_all_asset_scopes = retrieve_all_arl_asset_scopes(token, arl_url)
    for asset_scope in arl_all_asset_scopes:
        scope_id = asset_scope["_id"]
        domain = ",".join(asset_scope["scope_array"])
        # 找到对应的策略
        policy = next(
            (
                policy
                for policy in arl_all_policies
                if policy["policy"]["scope_config"]["scope_id"] == scope_id
            ),
            None,
        )
        if policy is not None:
            policy_id = policy["_id"]
            add_scheduler(token, arl_url, scope_id, domain, policy_id)
            add_site_monitor(token, arl_url, scope_id)  # 添加站点更新监控周期任务
        else:
            print(f"No policy found for scope_id {scope_id}")
    print("8-arl监控任务添加完毕,统计数据，脚本结束。")

    # 9. 在每次脚本运行结束后，统计双方互相同步的新资产分组数量，新同步的子域名数量、IP数量。
    new_asset_scopes_count = len(business_only_asset_scopes) + len(
        arl_only_asset_scopes
    )
    new_domains_count = len(new_domains_to_arl) + len(new_domains_to_bbdb)
    new_ips_count = len(new_ips_to_bbdb)

    print(f"New asset groups synced: {new_asset_scopes_count}")
    print(f"New domains synced: {new_domains_count}")
    print(f"New IPs synced: {new_ips_count}")


if __name__ == "__main__":
    main()
