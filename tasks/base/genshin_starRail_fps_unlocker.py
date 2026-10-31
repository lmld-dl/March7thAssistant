from module.config import cfg
from module.logger import log
import sys
import os
from utils.console import pause_on_error, pause_and_retry


class Genshin_StarRail_fps_unlocker:
    @staticmethod
    def update():
        from tasks.base.download import download_with_progress
        from tasks.base.fastest_mirror import FastestMirror
        import requests
        import json
        response = requests.get(FastestMirror.get_github_api_mirror("winTEuser", "Genshin_StarRail_fps_unlocker"), timeout=10, headers=cfg.useragent)
        if response.status_code == 200:
            data = json.loads(response.text)
            url = None
            for asset in data["assets"]:
                if asset["name"].startswith("Unlocker") and asset["name"].endswith(".exe"):
                    url = FastestMirror.get_github_mirror(asset["browser_download_url"])
                    break
            if url is None:
                log.error("没有找到可用更新，请稍后再试")
                pause_on_error()
                sys.exit(0)
            os.makedirs(cfg.genshin_starRail_fps_unlocker_path, exist_ok=True)
            download_file_path = os.path.join(cfg.genshin_starRail_fps_unlocker_path, "unlocker.exe")
            if os.path.exists(download_file_path):
                try:
                    os.remove(download_file_path)
                except Exception as e:
                    log.warning(f"无法删除已有解锁器: {e}")
            log.info(f"开始下载: {url}")
            download_with_progress(url, download_file_path)
            log.info(f"下载完成: {download_file_path}")
        else:
            log.error(f"获取更新信息失败：{response.status_code}")
