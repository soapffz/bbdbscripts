# 作者: soapffz
# 创建时间: 2024年2月21日
# 最后更新时间: 2024年3月20日
# 描述: 自动登录雷神众测平台，获取并更新token，统计进行中项目信息，自动加入项目并推送bark

import os
import poplib
from email.parser import BytesParser
from email.policy import default
import re
from bs4 import BeautifulSoup
import requests
import json
import base64
import time


HOST = "pop.qq.com"
USER = os.getenv("QQMAIL_MAIL")
PASSWORD = os.getenv("QQMAIL_PASSWORD")
SEARCH_SUBJECT = "雷神众测"
QL_URL = "http://127.0.0.1:5700"
QL_CLIENT_ID = os.getenv("APP_BBDB_THOR_CLIENTID")
QL_CLIENT_SECRET = os.getenv("APP_BBDB_THOR_CLIENTSECERT")
ENV_NAME = "BBDB_THOR_AUTHORIZATION"
LOGIN_EMAIL = os.getenv("QQMAIL_MAIL")
LOGIN_ENCRTPT_PASSWORD = os.getenv("BBDB_THOR_ENCRYPT_PASSWORD")
OCR_API_SERVER_URL = os.getenv("OCR_API_SERVER_URL")


def log_message(message, is_positive=True):
    """打印日志信息"""
    prefix = "[ + ]" if is_positive else "[ - ]"
    print(f"{datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')} {prefix} {message}")

def check_environment_variables():
    """检查所有必要的环境变量是否已设置"""
    env_vars = [
        "QQMAIL_MAIL", "QQMAIL_PASSWORD", "APP_BBDB_THOR_CLIENTID",
        "APP_BBDB_THOR_CLIENTSECERT", "BBDB_THOR_AUTHORIZATION",
        "BBDB_THOR_ENCRYPT_PASSWORD","OCR_API_SERVER_URL"
    ]
    missing_vars = [var for var in env_vars if not os.getenv(var)]
    if missing_vars:
        for var in missing_vars:
            log_message(f"环境变量 {var} 未设置。", False)
        return False
    return True

def check_ocr_api_server():
    """检查OCR API服务器是否可访问"""
    try:
        response = requests.get(OCR_API_SERVER_URL)
        if response.status_code == 200:
            return True
        else:
            log_message("OCR API服务器无法访问，请检查。", False)
            log_message("使用 docker run -p 9898:9898 --name ocr_api_server -d esme518/ocr_api_server:latest 搭建验证码服务再继续。", False)
            return False
    except requests.RequestException:
        log_message("OCR API服务器无法访问，请检查。", False)
        log_message("使用 docker run -p 9898:9898 --name ocr_api_server -d esme518/ocr_api_server:latest 搭建验证码服务再继续。", False)
        return False

def get_captcha_result(image_base64):
    """
    使用OCR API服务识别验证码。
    """
    if not OCR_API_SERVER_URL:
        log_message("OCR_API_SERVER_URL环境变量未设置。", False)
        return None

    try:
        # 发送base64编码的图片数据到OCR API
        resp = requests.post(OCR_API_SERVER_URL, data=image_base64)
        resp.raise_for_status()  # 确保HTTP请求成功

        # 解析响应数据
        result = resp.json()
        if result.get("status") == 200:
            captcha_text = result.get("result")
            if captcha_text:
                return captcha_text
            else:
                log_message("验证码识别失败，未返回文本。", False)
                return None
        else:
            log_message(f"验证码识别失败，状态码：{result.get('status')}, 消息：{result.get('msg')}", False)
            return None
    except requests.RequestException as error:
        log_message(f"请求OCR API服务失败: {error}", False)
        return None


def login_and_update_token():
    """
    登录并更新token环境变量。
    """
    # 获取验证码图片
    captcha_response = requests.get("https://www.bountyteam.com/web/v1/imageCode")
    captcha_data = captcha_response.json()
    if captcha_data["errcode"] == 0:
        image_base64 = captcha_data["ret"]["photo"].split(",")[-1]
        captcha_code = captcha_data["ret"]["code"]
        photoCode = get_captcha_result(image_base64)
        if photoCode:
            # 发送邮件验证码
            email = USER
            email_code_url = f"https://www.bountyteam.com/web/v1/portal/emailcode?email={email}&photoCode={photoCode}&code={captcha_code}"
            email_code_response = requests.get(email_code_url)
            email_code_data = email_code_response.json()
            if email_code_data["errcode"] == 0:
                log_message(
                    f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 邮件验证码发送成功。"
                )
                # 获取邮件验证码
                time.sleep(10)
                email_verification_code = (
                    fetch_verification_code()
                )  # 假设这个函数能够获取到邮件中的验证码
                # 登录操作
                login_data = {
                    "checkcode": email_verification_code,
                    "password": LOGIN_ENCRTPT_PASSWORD,
                    "email": email,
                }
                login_response = requests.post(
                    "https://www.bountyteam.com/web/v1/portal/login", json=login_data
                )
                login_data = login_response.json()
                if login_data["errcode"] == 0:
                    token = login_data["ret"]["token"]
                    # 更新环境变量
                    if update_env_variable(token):  # 更新环境变量
                        log_message(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 登录成功，token已更新。"
                        )
                        return token
                else:
                    log_message(
                        f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录失败：",
                        login_data["errmsg"],
                    )
            else:
                print(
                    f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 邮件验证码发送失败：",
                    email_code_data["errmsg"],
                )
        else:
            log_message("验证码识别失败。")
    else:
        log_message("获取验证码失败：",
            captcha_data["errmsg"],
        )

def fetch_verification_code():
    """
    从QQ邮箱中获取验证码。
    """
    try:
        server = poplib.POP3_SSL(HOST)
        server.user(USER)
        server.pass_(PASSWORD)
        num_messages = len(server.list()[1])
        verification_code = None

        for i in range(num_messages, max(num_messages - 2, 0), -1):
            resp, lines, octets = server.retr(i)
            msg_content = b"\r\n".join(lines)
            msg = BytesParser(policy=default).parsebytes(msg_content)
            subject = str(msg["subject"])
            if SEARCH_SUBJECT in subject:
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/html":
                            html_body = part.get_payload(decode=True).decode("utf-8")
                            soup = BeautifulSoup(html_body, "html.parser")
                            code_match = re.search(
                                r"验证码是：\s*(\w+)", soup.get_text()
                            )
                            if code_match:
                                verification_code = code_match.group(1)
                                break
                else:
                    content_type = msg.get_content_type()
                    if content_type == "text/html":
                        html_body = msg.get_payload(decode=True).decode("utf-8")
                        soup = BeautifulSoup(html_body, "html.parser")
                        code_match = re.search(r"验证码是：\s*(\w+)", soup.get_text())
                        if code_match:
                            verification_code = code_match.group(1)
                if verification_code:
                    break

        server.quit()

        if verification_code:
            return verification_code
        else:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 未找到包含‘雷神众测’主题的邮件。"
            )
            return None

    except poplib.error_proto as e:
        log_message("邮件服务器错误: {str(e)}")
    except Exception as e:
        log_message("处理邮件时发生错误: {str(e)}"
        )
        return None

def access_project_list(token):
    """
    使用token访问项目列表页面，并打印除了通用漏洞奖励计划外的最新项目名称。
    """
    headers = {"Authorization": token}
    response = requests.get(
        "https://www.bountyteam.com/web/v1/project/getProjectList?size=20&page=1&search=&lastPush=1&projectType=&projectSubType=&status=&joinStatus=&ownership=",
        headers=headers,
    )
    project_list_data = response.json()
    if project_list_data["errcode"] == 0:
        log_message("项目列表获取成功。")
        projects = project_list_data.get("ret", {}).get("data", [])
        # 筛选出除了通用漏洞奖励计划外的项目
        non_common_vulnerability_projects = [
            project for project in projects if project.get("name") != "通用漏洞奖励计划"
        ]
        if non_common_vulnerability_projects:
            # 获取最新的一个项目名称
            latest_project_name = non_common_vulnerability_projects[0].get("name")
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 最新的项目名称为: {latest_project_name}"
            )
        else:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 没有找到符合条件的项目。"
            )
    else:
        log_message("访问项目列表失败：",
            project_list_data["errmsg"],
        )


def get_qinglong_openapi_token():
    """
    获取青龙面板的token。
    """
    url = f"{QL_URL}/open/auth/token?client_id={QL_CLIENT_ID}&client_secret={QL_CLIENT_SECRET}"
    response = requests.get(url)
    if response.status_code == 200:
        ql_token_data = response.json()
        return ql_token_data["data"]["token"]
    else:
        log_message("获取token失败，状态码：{response.status_code}，响应内容：{response.text}"
        )
        return None


def update_env_variable(env_value):
    """
    更新青龙面板的环境变量。
    """
    ql_token = get_qinglong_openapi_token()
    if ql_token is None:
        return False

    headers = {
        "Authorization": f"Bearer {ql_token}",
        "Content-Type": "application/json",
    }
    # 获取所有环境变量以找到需要更新的环境变量的_id
    get_envs_url = f"{QL_URL}/open/envs"
    response = requests.get(get_envs_url, headers=headers)
    if response.status_code != 200:
        log_message("获取环境变量失败，状态码：{response.status_code}，响应内容：{response.text}"
        )
        return False

    envs = response.json().get("data", [])
    env_id = None
    for env in envs:
        if env.get("name") == ENV_NAME:
            env_id = env.get("id")
            break
    if not env_id:
        log_message("未找到环境变量 {ENV_NAME}")
        return False

    # 更新指定的环境变量
    update_data = {
        "name": ENV_NAME,
        "value": env_value,
        "id": env_id,
    }
    update_response = requests.put(
        f"{QL_URL}/open/envs", headers=headers, json=update_data
    )
    if update_response.status_code == 200:
        log_message("环境变量 {ENV_NAME} 更新成功。"
        )
        return True
    else:
        log_message("更新环境变量失败，状态码：{update_response.status_code}，响应内容：{update_response.text}"
        )
        return False


def check_login_and_fetch_projects():
    """
    检查当前的登录状态，并获取进行中的项目信息。
    """
    token = os.getenv(ENV_NAME)
    if not token:
        log_message("未找到环境变量中的Authorization token。"
        )
        return False, []

    headers = {
        "Authorization": token,
        "Referer": "https://www.bountyteam.com/hackerservice/projectPage",
    }
    response = requests.get(
        "https://www.bountyteam.com/web/v1/project/getpersonalprojectList?size=20&page=1&projectSubType=&projectType=&status=&search=",
        headers=headers,
    )
    response_data = response.json()

    if response.status_code == 200 and response_data["errcode"] == 0:
        projects = response_data["ret"]["data"]
        ongoing_projects = [
            project for project in projects if project["states"] in ["doing", "apply"]
        ]
        log_message("当前已登录，并成功获取进行中和申请中的项目信息。"
        )
        return True, ongoing_projects
    elif response_data["errcode"] == 401:
        if response_data["errmsg"] in ["权限鉴定失败", "登录失败或未登录"]:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录失败或未登录，需要重新登录。"
            )
        else:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 未知错误，错误消息：{response_data['errmsg']}"
            )
        return False, []
    else:
        log_message("访问失败，错误码：{response_data['errcode']}，错误消息：{response_data['errmsg']}"
        )
        return False, []


def access_project_list_and_compare(token, my_projects):
    """
    访问项目列表页面，并与我的项目进行比较，尝试参加最新项目。
    排除掉通用漏洞奖励计划，其ID固定为9999。
    """
    headers = {
        "Authorization": token,
        "Referer": "https://www.bountyteam.com/hackerservice/projectPage",
    }
    response = requests.get(
        "https://www.bountyteam.com/web/v1/project/getProjectList?size=20&page=1&search=&lastPush=1&projectType=&projectSubType=&status=&joinStatus=&ownership=",
        headers=headers,
    )
    if response.status_code == 200 and response.json()["errcode"] == 0:
        projects = response.json()["ret"]["data"]
        # 过滤掉ID为9999的项目
        projects = [project for project in projects if project["id"] != 9999]
        if projects:  # 确保过滤后仍有项目
            for project in projects:
                if project["id"] in [p["id"] for p in my_projects]:
                    # 检查项目状态，区分已加入和申请中
                    if project["states"] == "apply":
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 最新项目：{project['name']} 已申请"
                        )
                    else:
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 您已加入当前最新项目：{project['name']}"
                        )
                    project_status_info = capture_project_status_info(
                        my_projects, token
                    )
                    print(project_status_info)
                    break  # 找到最新项目后退出循环
                else:
                    # 尝试加入项目的逻辑保持不变
                    sign_response = requests.get(
                        f"https://www.bountyteam.com/web/v1/project/hacker/signProject?id={project['id']}",
                        headers=headers,
                    )
                    if (
                        sign_response.status_code == 200
                        and sign_response.json()["errcode"] == 0
                    ):
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 成功申请加入项目：{project['name']}"
                        )
                        # 重新获取项目状态并打印
                        _, updated_projects = check_login_and_fetch_projects()
                        project_status_info = capture_project_status_info(
                            updated_projects, token
                        )
                        bark_push(
                            "雷神众测新项目申请通知",
                            f"雷神众测新项目申请成功\n\n{project_status_info}",
                        )
                        break  # 成功申请后退出循环
                    elif sign_response.json()["errcode"] == 200:
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 当前最新项目：{project['name']} 已申请"
                        )
                        # 不退出循环，继续检查下一个项目
                    else:
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 申请加入项目失败：{sign_response.json()['errmsg']}"
                        )
                        break  # 如果申请失败，退出循环
        else:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 没有找到符合条件的最新项目。"
            )
    else:
        log_message("获取项目列表失败。")


def capture_project_status_info(ongoing_projects, token):
    """
    获取进行中和申请中的项目状态信息，用于推送。
    """
    project_status_info = f"\n{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 项目状态：\n"
    headers = {
        "Authorization": token,
        "Referer": "https://www.bountyteam.com/hackerservice/projectPage",
    }
    for project in ongoing_projects:
        if project["states"] == "apply":
            project_status_info += f"【waiting 】【{project['name']}】申请中\n"
        elif project["states"] == "doing":
            response = requests.get(
                f"https://www.bountyteam.com/web/v1/project/getProjectdetail?id={project['id']}",
                headers=headers,
            )
            if response.status_code == 200:
                project_detail = response.json()
                if (
                    project_detail.get("errcode") == 0
                    and project_detail["ret"]["data"]["testRange"] is not None
                ):
                    project_status_info += f"{project['name']}，剩余天数 {project['surplus']} 天，奖金池进度 {project['progress']} %，{project['lowriskreward']}-{project['highriskreward']}\n"
        else:
            project_status_info += f"{project['name']}，剩余天数 {project['surplus']} 天，奖金池进度 {project['progress']} %，{project['lowriskreward']}-{project['highriskreward']}\n"
    return project_status_info


def bark_push(title, content):
    """
    使用Bark推送消息到iOS设备。
    """
    bark_key = os.getenv("BARK_GUANFANG_KEY")
    url = f"https://api.day.app/{bark_key}/{title}/{content}"
    response = requests.get(url)
    if response.status_code == 200:
        log_message("推送成功")
    else:
        log_message("推送失败")


def main():
    """
    主函数：检查登录状态并获取进行中的项目，登录并更新token，访问项目列表。
    """
    is_logged_in, my_projects = check_login_and_fetch_projects()
    if not is_logged_in:
        token = login_and_update_token()
        if not token:
            print(
                f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录操作失败，未能获取token。"
            )
            return
        else:
            # 如果登录成功并获取到了token，重新检查登录状态并获取进行中的项目
            _, my_projects = check_login_and_fetch_projects()
    else:
        # 如果已经登录，token应该已经设置在环境变量中
        token = os.getenv(ENV_NAME)

    # 假设access_project_list_and_compare函数需要token和我的项目列表作为参数
    access_project_list_and_compare(token, my_projects)


if __name__ == "__main__":
    main()
