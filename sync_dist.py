import os
import shutil
import subprocess
import argparse

def sync_dist_to_repo(source_dist_dir, target_repo_dir):
    target_data_dir = os.path.join(target_repo_dir, 'data', 'questions')
    
    os.makedirs(target_data_dir, exist_ok=True)
    
    images_src = os.path.join(source_dist_dir, 'images')
    images_dst = os.path.join(target_data_dir, 'images')
    
    if os.path.exists(images_src):
        if os.path.exists(images_dst):
            shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)
        print(f"已复制图片文件夹: {images_src} -> {images_dst}")
    else:
        print(f"警告: 源图片目录不存在: {images_src}")
    
    data_src = os.path.join(source_dist_dir, 'data')
    data_dst = os.path.join(target_data_dir, 'data')
    
    if os.path.exists(data_src):
        if os.path.exists(data_dst):
            shutil.rmtree(data_dst)
        shutil.copytree(data_src, data_dst)
        print(f"已复制数据文件夹: {data_src} -> {data_dst}")
    else:
        print(f"警告: 源数据目录不存在: {data_src}")

def push_to_github(repo_dir, commit_message="Update question bank data"):
    try:
        os.chdir(repo_dir)
        
        subprocess.run(['git', 'add', 'data/questions/'], check=True, capture_output=True)
        
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
        
        if not result.stdout.strip():
            print("没有检测到文件变更，跳过提交")
            return True
        
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, capture_output=True, text=True)
        print("已提交变更")
        
        subprocess.run(['git', 'push'], check=True, capture_output=True, text=True)
        print("成功推送到 GitHub！")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"Git 操作失败: {e}")
        if e.stderr:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
            print(f"错误详情: {stderr}")
        return False
    except Exception as e:
        print(f"推送失败: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='将 dist 文件夹同步到 GitHub 仓库')
    parser.add_argument('--source-dir', default=r'P:\documents\AMC8\dist',
                        help='dist 文件夹所在路径')
    parser.add_argument('--repo-dir', default=os.getcwd(),
                        help='GitHub 仓库本地路径')
    parser.add_argument('--no-push', action='store_true',
                        help='只复制文件，不推送到 GitHub')
    
    args = parser.parse_args()
    
    print(f"源目录: {args.source_dir}")
    print(f"目标仓库: {args.repo_dir}")
    
    if not os.path.exists(args.source_dir):
        print(f"错误: 源目录不存在: {args.source_dir}")
        exit(1)
    
    if not os.path.exists(os.path.join(args.repo_dir, '.git')):
        print(f"错误: 目标目录不是 Git 仓库: {args.repo_dir}")
        exit(1)
    
    sync_dist_to_repo(args.source_dir, args.repo_dir)
    
    if not args.no_push:
        print("\n正在推送到 GitHub...")
        push_to_github(args.repo_dir)