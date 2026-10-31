import urllib.request
import subprocess
import os

from utils.progress import ProgressBar


def download_with_progress(download_url, save_path, use_update_proxy=False):
    """下载文件并显示进度。use_update_proxy 保留签名以兼容旧调用，精简客户端统一走系统代理。"""
    del use_update_proxy

    aria2_path = os.path.abspath("./assets/binary/aria2c.exe")
    proxies = urllib.request.getproxies()

    if os.path.exists(aria2_path):
        command = [
            aria2_path,
            "--disable-ipv6=true",
            "--dir={}".format(os.path.dirname(save_path)),
            "--out={}".format(os.path.basename(save_path)),
        ]
        if "github.com" in download_url:
            command.insert(2, "--max-connection-per-server=16")
            if os.path.exists(save_path):
                command.insert(2, "--continue=true")
        for scheme, proxy in proxies.items():
            if scheme in ("http", "https", "ftp"):
                command.append(f"--{scheme}-proxy={proxy}")
        command.append(download_url)
        subprocess.run(command, check=True)
    else:
        response = urllib.request.urlopen(download_url)
        file_size = int(response.info().get('Content-Length', -1))

        with ProgressBar(total=file_size) as pbar:
            def update_bar(block_count, block_size, total_size):
                if pbar.total != total_size:
                    pbar.total = total_size
                downloaded = block_count * block_size
                pbar.update(downloaded - pbar.n)

            urllib.request.urlretrieve(download_url, save_path, reporthook=update_bar)
