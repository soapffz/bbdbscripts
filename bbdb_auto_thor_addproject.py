# 作者: soapffz
# 创建时间: 2024年2月21日
# 最后更新时间: 2024年2月22日
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
YUNMA_TOKEN = os.getenv("YUNMA_TOKEN")
YUNMA_BBDB_THOR_TYPECODE = os.getenv("YUNMA_BBDB_THOR_TYPECODE")


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
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 邮件服务器错误: {str(e)}")
    except Exception as e:
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 处理邮件时发生错误: {str(e)}"
        )
        return None


def get_captcha_result(image_base64, token, type_code):
    """
    向验证码识别服务发送请求，并返回识别结果。
    """
    data = {"token": token, "type": type_code, "image": image_base64}
    headers = {"Content-Type": "application/json"}
    url = "http://api.jfbym.com/api/YmServer/customApi"
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # 确保HTTP请求成功
        return response.json()
    except requests.RequestException as error:
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 请求验证码识别服务失败: {error}"
        )
        return None


def login_and_update_token(token, type_code):
    """
    登录并更新token环境变量。
    """
    # 获取验证码图片
    captcha_response = requests.get("https://www.bountyteam.com/web/v1/imageCode")
    captcha_data = captcha_response.json()
    if captcha_data["errcode"] == 0:
        image_base64 = captcha_data["ret"]["photo"].split(",")[-1]
        captcha_code = captcha_data["ret"]["code"]
        # 调用get_captcha_result时传入token和type_code
        captcha_result = get_captcha_result(image_base64, token, type_code)
        if (
            captcha_result
            and captcha_result["code"] == 10000
            and "data" in captcha_result
        ):
            photoCode = captcha_result["data"]["data"]
            # 发送邮件验证码
            email = USER
            email_code_url = f"https://www.bountyteam.com/web/v1/portal/emailcode?email={email}&photoCode={photoCode}&code={captcha_code}"
            email_code_response = requests.get(email_code_url)
            email_code_data = email_code_response.json()
            if email_code_data["errcode"] == 0:
                print(
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
                        print(
                            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 登录成功，token已更新。"
                        )
                        return token
                else:
                    print(
                        f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录失败：",
                        login_data["errmsg"],
                    )
            else:
                print(
                    f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 邮件验证码发送失败：",
                    email_code_data["errmsg"],
                )
        else:
            print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 验证码识别失败。")
    else:
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 获取验证码失败：",
            captcha_data["errmsg"],
        )


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
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 项目列表获取成功。")
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
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 访问项目列表失败：",
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
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 获取token失败，状态码：{response.status_code}，响应内容：{response.text}"
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
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 获取环境变量失败，状态码：{response.status_code}，响应内容：{response.text}"
        )
        return False

    envs = response.json().get("data", [])
    env_id = None
    for env in envs:
        if env.get("name") == ENV_NAME:
            env_id = env.get("id")
            break
    if not env_id:
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 未找到环境变量 {ENV_NAME}")
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
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 环境变量 {ENV_NAME} 更新成功。"
        )
        return True
    else:
        print(
            f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 更新环境变量失败，状态码：{update_response.status_code}，响应内容：{update_response.text}"
        )
        return False


def check_login_and_fetch_projects():
    """
    检查当前的登录状态，并获取进行中的项目信息。
    """
    token = os.getenv(ENV_NAME)
    if not token:
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 未找到环境变量中的Authorization token。")
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
        ongoing_projects = [project for project in projects if project["states"] == "doing"]
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 当前已登录，并成功获取进行中的项目信息。")
        return True, ongoing_projects
    elif response_data["errcode"] == 401:
        if response_data["errmsg"] in ["权限鉴定失败", "登录失败或未登录"]:
            print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录失败或未登录，需要重新登录。")
        else:
            print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 未知错误，错误消息：{response_data['errmsg']}")
        return False, []
    else:
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 访问失败，错误码：{response_data['errcode']}，错误消息：{response_data['errmsg']}")
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
            latest_project = projects[0]  # 假设第一个项目是最新的
            if latest_project["id"] in [p["id"] for p in my_projects]:
                print(f"您已加入当前最新项目：{latest_project['name']}")
            else:
                print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 尝试加入最新项目：{latest_project['name']}")
                # 此处省略参加项目的代码，假设已实现
                # 如果参加成功，可以调用access_my_project_list(token)重新获取我的项目列表
        else:
            print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 没有找到符合条件的最新项目。")
    else:
        print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 获取项目列表失败。")


def print_ongoing_projects(ongoing_projects):
    """
    打印进行中的项目状态。
    """
    print(f"\n{time.strftime('%Y-%m-%d-%H-%M-%S')} [ + ] 进行中项目状态：")
    for project in ongoing_projects:
        print(
            f"{project['name']}，剩余天数 {project['surplus']} 天，奖金池进度 {project['progress']} %，{project['lowriskreward']}-{project['highriskreward']}"
        )


def bark_push(title, content):
    """
    使用Bark推送消息到iOS设备。
    """
    bark_key = os.getenv("BARK_GUANFANG_KEY")
    url = f"https://api.day.app/{bark_key}/{title}/{content}"
    response = requests.get(url)
    if response.status_code == 200:
        print("推送成功")
    else:
        print("推送失败")


def main():
    """
    主函数：检查登录状态并获取进行中的项目，登录并更新token，访问项目列表。
    """
    is_logged_in, my_projects = check_login_and_fetch_projects()
    if not is_logged_in:
        token = login_and_update_token(YUNMA_TOKEN, YUNMA_BBDB_THOR_TYPECODE)
        if not token:
            print(f"{time.strftime('%Y-%m-%d-%H-%M-%S')} [ - ] 登录操作失败，未能获取token。")
            return
        else:
            # 如果登录成功并获取到了token，重新检查登录状态并获取进行中的项目
            _, my_projects = check_login_and_fetch_projects()
    else:
        # 如果已经登录，token应该已经设置在环境变量中
        token = os.getenv(ENV_NAME)

    # 假设access_project_list_and_compare函数需要token和我的项目列表作为参数
    access_project_list_and_compare(token, my_projects)
    # 打印进行中的项目信息
    print_ongoing_projects(my_projects)
    # 如果加入了新的项目，可以在这里调用bark_push进行推送

if __name__ == '__main__':
    main()
