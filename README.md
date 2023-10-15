## NaN.1 目录

_个人自用_

## NaN.2 BBDBSCRIPTS

`BB` 是 `bugbounty` 的缩写

项目背景：网络资产搜索工具繁多，更新换代快，做好 bugbounty 资产持续性收集及存储是有必要的.

项目目的：与常用 `bugbounty`/`SRC`/`众测` 资产搜集工具联动，双向数据聚合，拓宽企业/组织/众测资产的广度。

数据库选型：经咨询 `Cursor`中的 `FAST GPT-4`，选定 `MongoDB`，`docker` 容器类型，版本选择最新的 `LTS` 版本 `4.4` 版本，如果用 [Digitalocean](digitalocean.com) 只创建 `mongo` 也是可以选择这个版本的

## NaN.3 此仓库脚本使用方式

所有脚本都在开头注释中解释了详细用法

部分脚本使用[青龙定时平台](https://github.com/whyour/qinglong)处理

### NaN.3.1 青龙脚本拉取及环境变量设置

#### 拉取方式

```
ql repo https://github.com/soapffz/bbdbscripts.git "bbdb_*.py" "README.md"
```

- 拉取所有以"bbdb\_"开头，后缀为".py"的文件，同时排除"README.md"文件

#### 青龙变量清单

- `BBDB_ARL_API_URL`:
- `BBDB_ARL_API_KEY`:
- `BBDB_MONGODB_URI`: mongodb 连接的字符串，格式为：mongodb+srv://用户名:密码@数据库地址/"
- `BBDB_API_SHODAN`: [Shodan](https://www.shodan.io/)的 `API`
- `BBDB_API_QUAKE`: [360 Quake](https://quake.360.net/quake/#/index) 的 `API`
- `BBDB_API_FOFA_MAIL`: [FOFA](https://fofa.info/) 的邮箱
- `BBDB_API_FOFA_API`: [FOFA](https://fofa.info/) 的的`API`
- `BBDB_API_HUNTER`: [奇安信鹰图 HUNTER](https://hunter.qianxin.com/home/userInfo)的`API`
- `BBDB_API_ZOOMEYE_MAIL`: [Zoomeye](https://www.zoomeye.org/)的 邮箱
- `BBDB_API_ZOOMEYE_PASSWORD`: [Zoomeye](https://www.zoomeye.org/)的 密码
- `BBDB_API_ZOOMEYE_API`: [Zoomeye](https://www.zoomeye.org/)的 `API`

长期使用可以维护一个`env.json`，在青龙面板环境变量菜单批量导入导出，注意没有的空字段删除后再上传

<details>
<summary>env.json模版</summary>

```
[
    {
        "name": "BBDB_ARL_API_URL",
        "value": "",
        "remarks": "ARL API URL"
    },
    {
        "name": "BBDB_ARL_API_KEY",
        "value": "",
        "remarks": "ARL API Key"
    },
    {
        "name": "BBDB_MONGODB_HOST",
        "value": "",
        "remarks": "MongoDB Host"
    },
    {
        "name": "BBDB_MONGODB_PORT",
        "value": "",
        "remarks": "MongoDB Port"
    },
    {
        "name": "BBDB_MONGODB_DB",
        "value": "",
        "remarks": "MongoDB Database"
    },
    {
        "name": "BBDB_MONGODB_USER",
        "value": "",
        "remarks": "MongoDB User"
    },
    {
        "name": "BBDB_MONGODB_PASSWORD",
        "value": "",
        "remarks": "MongoDB Password"
    },
    {
        "name": "BBDB_API_SHODAN",
        "value": "",
        "remarks": "Shodan API"
    },
    {
        "name": "BBDB_API_QUAKE",
        "value": "",
        "remarks": "360 Quake API"
    },
    {
        "name": "BBDB_API_FOFA_MAIL",
        "value": "",
        "remarks": "FOFA Mail"
    },
    {
        "name": "BBDB_API_FOFA_API",
        "value": "",
        "remarks": "FOFA API"
    },
    {
        "name": "BBDB_API_HUNTER",
        "value": "",
        "remarks": "奇安信鹰图 HUNTER API"
    },
    {
        "name": "BBDB_API_ZOOMEYE_MAIL",
        "value": "",
        "remarks": "Zoomeye Mail"
    },
    {
        "name": "BBDB_API_ZOOMEYE_PASSWORD",
        "value": "",
        "remarks": "Zoomeye Password"
    },
    {
        "name": "BBDB_API_ZOOMEYE_API",
        "value": "",
        "remarks": "Zoomeye API"
    }
]
```

</details>

## NaN.4 数据库启动及初始化

### NaN.4.1 docker

```shell
docker run -d -p 27017:27017 -v ～/bugbountymongodbdata/db --name bbmongodb mongo:4.4
```

### NaN.4.2 mac m1 上

```shell
brew tap mongodb/brew && brew install mongodb-community@4.4 && brew services start mongodb-community@4.4 && mongorestore --drop --uri="mongodb://localhost:27017" 你的备份文件
```

本地调试灰常快，建议本地调试好了再上远程

## NaN.5 备份方式

1. 在 docker 容器运行的机器上映射到主机本地目录/直接用云服务商提供的数据库服务做第 1 次备份

2. 定时备份数据库到云盘做第 2 次备份

3. 本地使用时同步一份做第 3 次备份

## NaN.6 维护数据库的原则

1. 只收集在 SRC 赏金范围内的资产，超过范围的定期手动删除

## NaN.7 数据库资产类型设计

数据库名称:`bbdb`

<details>
<summary>bbdb数据库设计</summary>

1. 业务表（business）

- id：业务 ID，MongoDB 自动生成
- name：业务名称，如项目名称/SRC 名称/公司名称/组织名称
- url：业务对应的链接
- company: 对应的公司名称，字符串列表
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

2. 根域名表（root_domain）

- _id：根域名 ID，MongoDB 自动生成
- name：根域名名称
- icpregnum：icp 备案号名称
- company: 主办单位名称
- company_type: 单位性质
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

3. 子域名表（sub_domain）

- _id：子域名 ID，MongoDB 自动生成
- name：子域名名称
- icpregnum：icp 备案号名称
- company: 主办单位名称
- company_type: 单位性质
- root_domain_id：关联的根域名 ID
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

4. 站点表（site）

- _id：站点 ID，MongoDB 自动生成
- url：站点 URL
- status：状态码
- title：网站标题
- keywords: 网站关键词，字符串列表
- applications: 应用名称，字符串列表
- applications_categories: 应用类别，字符串列表
- applications_types: 应用类型，字符串列表
- applications_levels: 应用层级，字符串列表
- application_manufacturer: 应用生产厂商，字符串列表
- fingerprint：网站指纹
- root_domain_id：关联的根域名 ID
- sub_domain_id：关联的子域名 ID
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

5. IP 地址表（ip）

- _id：IP 地址 ID，MongoDB 自动生成
- address：IP 地址
- port：端口号
- service_name：服务名称，如 Threema
- service_type：服务类型，如 http、ssl、default/xmpp-client 等
- service_desc：服务描述，如 nginx
- province_cn: 省份中文名称
- city_cn: 城市中文名称
- country_cn: 国家中文名称
- districts_and_counties_en: 区县英文名称
- districts_and_counties_cn: 区县中文名称
- province_en: 城市英文名称
- city_en: 城市英文名称
- country_en: 国家英文名称
- operators: 运营商名称
- is_real：是否为真实 IP
- is_cdn：是否为 CDN IP
- cname：如果为 CDN IP，补充 CNAME 地址字段
- root_domain_id：关联的根域名 ID
- sub_domain_id：关联的子域名 ID
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

6. 微信公众号表（wechat_public_account）

- _id：微信公众号 ID，MongoDB 自动生成
- name：微信公众号名称
- wechatid：微信公众号 ID
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- wechat_public_pic_url：微信公众号头像图片链接
- avatar_pic_url：头像图片链接
- create_time：创建时间
- update_time：修改时间

7. 小程序表（mini_program）

- _id：小程序 ID，MongoDB 自动生成
- name：小程序名称
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- avatar_pic_url：头像图片链接
- create_time：创建时间
- update_time：修改时间

8. APP 表（app）

- _id：APP ID，MongoDB 自动生成
- name：APP 名称
- type: APP 分类
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- avatar_pic_url：头像图片链接
- create_time：创建时间
- update_time：修改时间

9. MAIL 表（mail）

- _id：MAIL ID，MongoDB 自动生成
- name：邮件地址
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

10. 软件著作权表（software_copyright）

- _id：software_copyright ID，MongoDB 自动生成
- name：software_copyright 名称
- regnumber：软件著作权注册 ID
- release_date：软件发布时间
- type：软件类型
- company: 主办单位名称
- company_type: 单位性质
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

11. 数据包表（data_packet）

- _id：数据包 ID，MongoDB 自动生成
- request：原始请求报文
- response：返回报文
- protocol：协议，字符串类型
- is_vuln：是否包含漏洞
- root_domain_id：关联的根域名 ID
- sub_domain_id：关联的子域名 ID
- ip_address_id：关联的 IP 地址 ID
- business_id：关联的业务 ID
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

12. Github 项目监测表（github_project_monitor）

- _id：项目 ID，MongoDB 自动生成
- url：项目链接
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

13. Github 用户/组织监测表（github_user_organization_monitor）

- _id：用户/组织 ID，MongoDB 自动生成
- name：用户/组织名称
- notes：备注，用于自定义描述
- create_time：创建时间
- update_time：修改时间

14. 黑名单表(blacklist)

- _id：黑名单 ID，MongoDB 自动生成
- type：黑名单类型，business/root_domain/sub_domain
- root_domain_id：关联的根域名 ID
- sub_domain_id：关联的子域名 ID
- business_id：关联的业务 ID
- create_time：创建时间
- update_time：修改时间

</details>

## NaN.8 数据库初始化

- 资产快速提取可以使用我写的[asset_processing.py](https://github.com/soapffz/hackscripts/blob/main/asset_processing.py)

- MongoDB 是一个 NoSQL 数据库，它不使用 SQL 作为查询语言，而是使用 JavaScript。

- 在 MongoDB 中，我们不需要预先创建数据库结构，因为它是一个基于文档的数据库，可以在运行时动态添加字段。 但是，我们可以使用 Mongoose 这样的库在 Node.js 中定义数据模型，或者在 Python 中使用 MongoEngine 或 PyMongo 这样的库来定义数据模型。

- 以下是使用 Python 的 PyMongo 库创建这些集合和索引的示例代码

<details>
<summary>bbdb数据库初始化</summary>

```python
from pymongo import MongoClient, IndexModel, ASCENDING

# 连接MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['bbdb']

# 创建业务集合
business_collection = db['business']
business_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("url", ASCENDING)])])

# 创建根域名集合
root_domain_collection = db['root_domain']
root_domain_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建子域名集合
sub_domain_collection = db['sub_domain']
sub_domain_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("root_domain_id", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建站点集合
site_collection = db['site']
site_collection.create_indexes([IndexModel([("url", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建IP地址集合
ip_address_collection = db['ip_address']
ip_address_collection.create_indexes([IndexModel([("address", ASCENDING)]), IndexModel([("root_domain_id", ASCENDING)]), IndexModel([("sub_domain_id", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建微信公众号集合
wechat_public_account_collection = db['wechat_public_account']
wechat_public_account_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建小程序集合
mini_program_collection = db['mini_program']
mini_program_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建APP集合
app_collection = db['app']
app_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建邮件集合
mail_collection = db['mail']
mail_collection.create_indexes([IndexModel([("mail", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建软件著作权集合
software_copyright_collection = db['software_copyright']
software_copyright_collection.create_indexes([IndexModel([("name", ASCENDING)]), IndexModel([("regnumber", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建数据包集合
data_packet_collection = db['data_packet']
data_packet_collection.create_indexes([IndexModel([("root_domain_id", ASCENDING)]), IndexModel([("sub_domain_id", ASCENDING)]), IndexModel([("ip_address_id", ASCENDING)]), IndexModel([("business_id", ASCENDING)])])

# 创建Github项目监测集合
github_project_monitor_collection = db['github_project_monitor']
github_project_monitor_collection.create_indexes([IndexModel([("url", ASCENDING)])])

# 创建Github用户/组织监测集合
github_user_organization_monitor_collection = db['github_user_organization_monitor']
github_user_organization_monitor_collection.create_indexes([IndexModel([("name", ASCENDING)])])

# 创建黑名单集合
blacklist_collection = db['blacklist']
blacklist_collection.create_indexes([IndexModel([("type", ASCENDING)]), IndexModel([("ref_id", ASCENDING)])])
```

</details>

## NaN.1 mongodump 和 mongorestore 备份和还原（比较过时）

- mongodump 和 mongorestore 命令在 MongoDB 4.4 版本中已被弃用，建议使用 mongocli 进行备份和恢复操作 \*

在本地[安装](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-os-x/) mongo 后使用 mongodump 备份数据库，使用 mongorestore 还原数据库

备份

```shell
mongodump --uri="mongo连接URI" --gzip --archive=backup.gz --numParallelCollections=4
```

还原

```shell
mongorestore --uri="mongo连接URI" --gzip --archive=backup.gz --numParallelCollections=4
```

- 使用--gzip 选项：这个选项可以让 mongodump 在下载数据的同时进行压缩，这样可以减少需要下载的数据量，可能会加快备份速度
- 使用--archive 选项：这个选项可以让 mongodump 将所有数据备份到一个文件中，而不是创建一个包含多个文件的目录。这样可以减少磁盘 I/O 操作，可能会加快备份速度。
- 使用--numParallelCollections 选项：这个选项可以让 mongodump 并行备份多个集合，这样可以利用多核 CPU，可能会加快备份速度。

ps：这里有个小技巧，还原并不是字面意思理解的覆盖，会逐条比较并把没有的 documents 插入进去，所以非常耗时间

实测 11w 条数据就需要 25 分钟以上，还原回去的数据也是乱的，还不如直接删库再恢复，实测只要 46 秒

附上删库脚本

```python
from pymongo import MongoClient

# NaN 连接MongoDB
client = MongoClient(
    "URI"
)

# NaN 删除bbdb数据库
client.drop_database("bbdb")
print("Database 'bbdb' deleted.")

```

## NaN.1 MongoDB CLI 备份和还原(支持的环境下可以尝试，我的不支持)

首先，你需要安装并配置 MongoDB CLI。你可以在 MongoDB 的官方文档中找到安装和配置的详细步骤。

安装完成后，你可以使用以下命令进行备份和恢复：

1. 备份数据库

使用 mongocli atlas backups snapshots create 命令创建一个新的快照。你需要提供你的项目 ID 和集群名称：

>

这将创建一个新的快照，并返回一个快照 ID。你可以使用这个 ID 来下载快照。

2. 下载快照

使用 mongocli atlas backups snapshots download 命令下载一个快照。你需要提供你的项目 ID、集群名称和快照 ID：
.

这将下载一个名为 snapshot.tar.gz 的文件到当前目录。

3. 恢复数据库

使用 mongocli atlas backups restores start 命令恢复一个快照。你需要提供你的项目 ID、集群名称和快照 ID：

>

这将开始恢复过程。你可以使用 mongocli atlas backups restores list 命令查看恢复的状态。

注意：这些命令需要在你的系统 PATH 中。如果你使用的是 MongoDB 的官方安装包，那么这些命令应该已经在 PATH 中了。如果不在，你需要手动添加它们。

## NaN.2 相关脚本运行截图展示

![bbdb_arl.py](https://img.soapffz.com/soapsgithubimgs/bbdb_arl演示截图-2023年10月12日.png)

## NaN.3 参考的项目列表

- <https://github.com/Young873/Firefly-SRC>

## NaN.4 更新日志

2023 年 10 月 15 日

- [add]: 添加了 quake 导出数据导入 bbdb 的功能
- [add]: 添加了清理 bbdb 数据库的功能
- [update]: 更新了 bbdb 数据库设计及 readme

2023 年 10 月 12 日

- [update]: 修复 bbdb_arl.py 脚本的 bug,贴上运行成功的截图

2023 年 10 月 10 日

- [add]: 完成 arl 和 bbdb 的初步联动的命令行版，并在 github 发布此项目

2023 年 10 月 1 日

- [update]: 根据实际数据导入及问题分析，优化 bbdb 字段设计

2023 年 9 月 23 日

- [init]: 项目启动
