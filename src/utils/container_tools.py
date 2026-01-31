import os
import shutil
import subprocess
import hashlib
from d2c_logger import tlogger
import requests

JDK_ZIP = "jdk-17.0.12.jdk.zip"
JDK_VERIFY_FILE = "jdk_md5_verify"
JDK_TARGET_FOLDER = "/tmp"
REPO_URL = "git@code.byted.org:ugc-android/kmp-d2c-evaluate.git"
JDK_DOWNLOAD_URL = "https://tosv.byted.org/obj/atk/d2c/static/jdk-17.0.12.jdk.zip"


def md5_of_file(file_path: str) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd, cwd=None):
    tlogger().info(f"start run command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, cwd=cwd, text=True)
    if result.returncode != 0:
        raise Exception(
            f"Failed to execute command: {' '.join(cmd)}. Error: {result.stderr}"
        )

def unzip_jdk(jdk_zip_path: str):
    """Unzip JDK file to /tmp directory"""
    if not os.path.exists(jdk_zip_path):
        raise FileNotFoundError(f"JDK zip file not found: {jdk_zip_path}")
    
    jdk_folder = jdk_zip_path.removesuffix('.zip')
    unzip_command = ["unzip", "-oq", str(jdk_zip_path), "-d", "/tmp"]
    run_cmd(unzip_command)
    tlogger().info(f"Successfully unzipped JDK to: {jdk_folder}")


def download_jdk(workspace_directory: str):
    download_path = os.path.join(workspace_directory, JDK_ZIP)
    os.makedirs(JDK_TARGET_FOLDER, exist_ok=True)
    headers = {
        "Accept-Encoding": "identity",
    }

    with requests.get(
        JDK_DOWNLOAD_URL,
        stream=True,
        timeout=300,
        headers=headers
    ) as r:
        r.raw.decode_content = False

        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))

        with open(download_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)

        actual_size = os.path.getsize(download_path)
        if total and actual_size != total:
            raise RuntimeError(f"Size mismatch: {actual_size} != {total}")
        md5 = hashlib.md5(open(download_path, 'rb').read()).hexdigest()
        tlogger().info(f"Downloaded {download_path}, size={actual_size}, MD5={md5}")
        shutil.copy(download_path, os.path.join(JDK_TARGET_FOLDER, JDK_ZIP))
    tlogger().info("JDK downloaded successfully (original bytes preserved)")


def prepare_jdk(workspace_directory: str):
    md5_verify_path = os.path.join(workspace_directory, JDK_VERIFY_FILE)
    if not os.path.exists(md5_verify_path):
        raise FileNotFoundError(f"{md5_verify_path} not found in repo")
    expected_md5_value = open(md5_verify_path).read().strip()
    jdk_target_path = os.path.join(JDK_TARGET_FOLDER, JDK_ZIP)
    if os.path.exists(jdk_target_path):
        jdk_md5_value = md5_of_file(jdk_target_path)
        if expected_md5_value == jdk_md5_value:
            unzip_jdk(jdk_target_path)
            return
        else:
            tlogger().info(f"jdk file check failed, md5 of exist file is: {jdk_md5_value}, expect {expected_md5_value}")
    else:
        tlogger().info(f"jdk file not exist, dowoload from cdn")
    download_jdk(workspace_directory)
    unzip_jdk(jdk_target_path)


def prepare_container(workspace_directory: str):
    clone_command = ["git", "clone", "--depth", "1", REPO_URL, workspace_directory]
    run_cmd(clone_command, cwd=workspace_directory)
    prepare_jdk(workspace_directory)


if __name__ == "__main__":
    prepare_container("/Users/bytedance/")

