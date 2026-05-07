import os
import json
import base64
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

def upload_file_to_github(token, owner, repo, file_path, content, branch="main", message="Update file"):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    encoded_content = base64.b64encode(content.encode('utf-8') if isinstance(content, str) else content).decode('utf-8')
    
    response = requests.get(url, headers=headers)
    
    data = {
        "message": message,
        "content": encoded_content,
        "branch": branch
    }
    
    if response.status_code == 200:
        data["sha"] = response.json()["sha"]
        response = requests.put(url, headers=headers, json=data)
    else:
        response = requests.put(url, headers=headers, json=data)
    
    if response.status_code == 201 or response.status_code == 200:
        return True, None
    else:
        error_msg = f"HTTP {response.status_code}"
        try:
            error_data = response.json()
            if "message" in error_data:
                error_msg += f": {error_data['message']}"
            if "errors" in error_data:
                error_msg += f" - {str(error_data['errors'])}"
        except:
            pass
        return False, error_msg

def upload_directory_to_github(token, owner, repo, local_dir, github_path, branch="main"):
    files_to_upload = []
    
    for root, dirs, files in os.walk(local_dir):
        for file in files:
            local_file_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_file_path, local_dir)
            github_file_path = os.path.join(github_path, relative_path).replace("\\", "/")
            files_to_upload.append((local_file_path, github_file_path))
    
    print(f"共发现 {len(files_to_upload)} 个文件需要上传")
    
    success_count = 0
    failed_count = 0
    
    for local_path, github_path in tqdm(files_to_upload, desc="上传文件"):
        try:
            with open(local_path, 'rb') as f:
                content = f.read()
            
            file_name = os.path.basename(local_path)
            message = f"Add/Update {file_name}"
            
            success, error = upload_file_to_github(token, owner, repo, github_path, content, branch, message)
            if success:
                success_count += 1
            else:
                failed_count += 1
                print(f"上传失败: {github_path} - {error}")
        except Exception as e:
            failed_count += 1
            print(f"处理文件失败 {local_path}: {e}")
    
    print(f"\n上传完成！成功: {success_count}, 失败: {failed_count}")
    return success_count, failed_count

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='直接通过 GitHub API 上传文件')
    parser.add_argument('--token', help='GitHub Personal Access Token')
    parser.add_argument('--owner', default='hzhbeck7', help='GitHub 仓库所有者')
    parser.add_argument('--repo', default='AMC8-math-learner', help='GitHub 仓库名称')
    parser.add_argument('--source-dir', default=r'P:\documents\AMC8\dist', help='本地源目录')
    parser.add_argument('--github-path', default='data/questions', help='GitHub 目标路径')
    parser.add_argument('--branch', default='main', help='GitHub 分支')
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get('GITHUB_TOKEN')
    
    if not token:
        print("错误：未提供 GitHub Token")
        print("请通过 --token 参数或 GITHUB_TOKEN 环境变量提供")
        exit(1)
    
    if not os.path.exists(args.source_dir):
        print(f"错误：源目录不存在: {args.source_dir}")
        exit(1)
    
    print(f"源目录: {args.source_dir}")
    print(f"目标仓库: {args.owner}/{args.repo}")
    print(f"目标路径: {args.github_path}")
    print(f"分支: {args.branch}")
    print("\n开始上传...")
    
    upload_directory_to_github(token, args.owner, args.repo, args.source_dir, args.github_path, args.branch)

if __name__ == "__main__":
    main()