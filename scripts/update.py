import json
import os
import requests
import zipfile
import tempfile
import shutil
from pathlib import Path
import io

def repack_module(zip_url, repo_name):
    with tempfile.TemporaryDirectory() as temp_dir:
        # 下载zip文件
        response = requests.get(zip_url)
        zip_data = io.BytesIO(response.content)
        
        # 准备重新打包的目标目录
        repack_dir = f"src/{repo_name}"
        os.makedirs(repack_dir, exist_ok=True)
        repack_zip = os.path.join(repack_dir, "module.zip")
        
        # 直接读取原始zip并重新打包
        with zipfile.ZipFile(zip_data, 'r') as zip_ref, \
             zipfile.ZipFile(repack_zip, 'w', compression=zipfile.ZIP_STORED) as zip_out:
            
            # 遍历原始zip中的所有文件
            for item in zip_ref.infolist():
                try:
                    content = zip_ref.read(item.filename)
                    # 保持原始ZipInfo的所有属性
                    new_info = item
                    new_info.compress_type = zipfile.ZIP_STORED
                    # 写入新文件
                    zip_out.writestr(new_info, content)
                except Exception as e:
                    print(f"Warning: Error processing {item.filename}: {str(e)}")
                    continue
        
        # 添加验证步骤
        with zipfile.ZipFile(repack_zip, 'r') as zip_check:
            # 打印所有文件列表
            print(f"Repacked ZIP contents for {repo_name}:")
            for info in zip_check.namelist():
                print(f"  - {info}")
            
            # 特别检查 module.prop
            if 'module.prop' not in zip_check.namelist():
                print("Warning: module.prop not found in repacked ZIP!")
            
            try:
                # 尝试读取 module.prop
                module_prop = zip_check.read('module.prop')
                print("module.prop content:", module_prop.decode('utf-8'))
            except:
                print("Error reading module.prop")
        
        return f"https://raw.githubusercontent.com/misak10/mmrl-update/main/src/{repo_name}/module.zip"

def get_latest_release(repo_info):
    # 从URL中提取用户名和仓库名
    repo_url = repo_info["url"]
    keyword = repo_info["keyword"]
    repack = repo_info.get("repack", False)
    _, _, _, username, repo = repo_url.rstrip('/').split('/')
    
    # 获取 GitHub API token
    github_token = os.environ.get('GH_TOKEN')
    
    # 准备请求头
    headers = {}
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    # 调用GitHub API
    api_url = f"https://api.github.com/repos/{username}/{repo}/releases/latest"
    response = requests.get(api_url, headers=headers)
    
    if response.status_code == 200:
        release_data = response.json()
        
        # 根据关键词筛选zip文件
        zip_url = None
        if keyword:
            for asset in release_data["assets"]:
                if asset["name"].endswith(".zip") and keyword in asset["name"].lower():
                    zip_url = asset["browser_download_url"]
                    break
        else:
            # 如果没有关键词，取第一个zip文件
            zip_url = next((asset["browser_download_url"] for asset in release_data["assets"] 
                          if asset["name"].endswith(".zip")), None)
        
        if not zip_url:
            return None
            
        # 提取版本号并生成版本代码
        tag_name = release_data["tag_name"]
        try:
            # 尝试提取数字部分
            version_code = ''.join(filter(str.isdigit, tag_name))
            if not version_code:
                version_code = "1"  # 如果没有数字，使用默认值
            version_code = int(version_code)
        except ValueError:
            version_code = 1  # 如果转换失败，使用默认值
        
        # 如果需要重新打包
        if repack:
            zip_url = repack_module(zip_url, repo)
            
        update_info = {
            "version": tag_name,
            "versionCode": version_code,
            "zipUrl": zip_url,
            "changelog": "none"
        }
        
        repo_name = repo_url.split("/")[-1]
        changelog_path = f"src/{repo_name}/changelog.md"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(changelog_path), exist_ok=True)
        
        # 处理changelog
        if release_data.get("body"):
            # 保存changelog到文件
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write(release_data["body"])
        else:
            # 如果没有changelog，创建一个包含"none"的文件
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write("none")
        
        # 使用raw.githubusercontent.com的URL
        update_info["changelog"] = f"https://raw.githubusercontent.com/misak10/mmrl-update/main/src/{repo_name}/changelog.md"
        
        return update_info
    return None

def main():
    # 读取配置文件
    with open("config.json", "r") as f:
        config = json.load(f)
    
    # 处理每个仓库
    for repo_info in config["repositories"]:
        repo_name = repo_info["url"].split("/")[-1]
        update_info = get_latest_release(repo_info)
        
        if update_info:
            # 确保目录存在
            os.makedirs(f"src/{repo_name}", exist_ok=True)
            
            # 更新update.json
            with open(f"src/{repo_name}/update.json", "w") as f:
                json.dump(update_info, f, indent=2)

if __name__ == "__main__":
    main() 
