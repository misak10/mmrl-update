import json
import os
import requests
import zipfile
import tempfile
import shutil
from pathlib import Path
import io
from typing import Dict, Any, Optional

def log(msg: str):
    print(f"[update.py] {msg}")

def repack_module(zip_url: str, repo_name: str) -> Optional[str]:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            response = requests.get(zip_url, timeout=30)
            response.raise_for_status()
            zip_data = io.BytesIO(response.content)

            repack_dir = f"src/{repo_name}"
            os.makedirs(repack_dir, exist_ok=True)
            repack_zip = os.path.join(repack_dir, "module.zip")

            with zipfile.ZipFile(zip_data, 'r') as zip_ref, \
                 zipfile.ZipFile(repack_zip, 'w', compression=zipfile.ZIP_STORED) as zip_out:
                for item in zip_ref.infolist():
                    try:
                        content = zip_ref.read(item.filename)
                        new_info = item
                        new_info.compress_type = zipfile.ZIP_STORED
                        zip_out.writestr(new_info, content)
                    except Exception as e:
                        log(f"Warning: Error processing {item.filename}: {str(e)}")
                        continue

            with zipfile.ZipFile(repack_zip, 'r') as zip_check:
                log(f"Repacked ZIP contents for {repo_name}:")
                for info in zip_check.namelist():
                    log(f"  - {info}")
                if 'module.prop' not in zip_check.namelist():
                    log("Warning: module.prop not found in repacked ZIP!")
                try:
                    module_prop = zip_check.read('module.prop')
                    log(f"module.prop content: {module_prop.decode('utf-8')}")
                except Exception:
                    log("Error reading module.prop")
            return f"https://raw.githubusercontent.com/misak10/mmrl-update/main/src/{repo_name}/module.zip"
    except Exception as e:
        log(f"[repack_module] Failed: {e}")
        return None

def get_latest_release(repo_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    repo_url = repo_info.get("url")
    keyword = repo_info.get("keyword", "")
    repack = repo_info.get("repack", False)
    if not repo_url or not isinstance(repo_url, str):
        log("Invalid repo url in config.")
        return None
    try:
        _, _, _, username, repo = repo_url.rstrip('/').split('/')
    except Exception:
        log(f"Invalid repo url format: {repo_url}")
        return None
    github_token = os.environ.get('GH_TOKEN')
    headers = {'Authorization': f'token {github_token}'} if github_token else {}
    api_url = f"https://api.github.com/repos/{username}/{repo}/releases/latest"
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code != 200:
            log(f"GitHub API error: {response.status_code} {response.text}")
            return None
        release_data = response.json()
        zip_url = None
        if keyword:
            for asset in release_data.get("assets", []):
                if asset["name"].endswith(".zip") and keyword in asset["name"].lower():
                    zip_url = asset["browser_download_url"]
                    break
        else:
            zip_url = next((asset["browser_download_url"] for asset in release_data.get("assets", []) if asset["name"].endswith(".zip")), None)
        if not zip_url:
            log(f"No zip asset found for {repo_url}")
            return None
        tag_name = release_data.get("tag_name", "v1.0")
        try:
            version_code = int(''.join(filter(str.isdigit, tag_name)) or "1")
        except Exception:
            version_code = 1
        if repack:
            zip_url = repack_module(zip_url, repo)
            if not zip_url:
                log(f"Repack failed for {repo}")
                return None
        update_info = {
            "version": tag_name,
            "versionCode": version_code,
            "zipUrl": zip_url,
            "changelog": "none"
        }
        repo_name = repo_url.split("/")[-1]
        changelog_path = f"src/{repo_name}/changelog.md"
        os.makedirs(os.path.dirname(changelog_path), exist_ok=True)
        changelog_body = release_data.get("body", "none")
        try:
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write(changelog_body)
        except Exception as e:
            log(f"Failed to write changelog: {e}")
        update_info["changelog"] = f"https://raw.githubusercontent.com/misak10/mmrl-update/main/src/{repo_name}/changelog.md"
        return update_info
    except Exception as e:
        log(f"[get_latest_release] Failed: {e}")
        return None

def validate_config(config: Dict[str, Any]) -> bool:
    if not isinstance(config, dict):
        log("Config is not a dict.")
        return False
    if "repositories" not in config or not isinstance(config["repositories"], list):
        log("Config missing 'repositories' list.")
        return False
    return True

def main():
    config_path = "config.json"
    if not os.path.exists(config_path):
        log(f"Config file not found: {config_path}")
        return
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        log(f"Failed to load config.json: {e}")
        return
    if not validate_config(config):
        return
    for repo_info in config["repositories"]:
        repo_name = repo_info.get("url", "").split("/")[-1]
        update_info = get_latest_release(repo_info)
        if update_info:
            try:
                os.makedirs(f"src/{repo_name}", exist_ok=True)
                with open(f"src/{repo_name}/update.json", "w", encoding="utf-8") as f:
                    json.dump(update_info, f, indent=2, ensure_ascii=False)
                log(f"Updated {repo_name} successfully.")
            except Exception as e:
                log(f"Failed to write update.json for {repo_name}: {e}")
        else:
            log(f"Failed to update {repo_name}.")

if __name__ == "__main__":
    main() 
