#!/bin/bash

# 进入git仓库目录
cd /ql/git_trickest_inventory

git reset --hard origin/main
git clean -df
# 为这次会话设置git代理
git config --global http.proxy http://192.168.2.252:7890
git config --global https.proxy http://192.168.2.252:7890

# 执行git pull
git pull

# 清除git代理设置，避免影响其他操作
git config --global --unset http.proxy
git config --global --unset https.proxy
