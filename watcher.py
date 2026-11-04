import time
import sys
from pathlib import Path
from importer import sync_watch_folder, load_config

def main():
    cfg = load_config()
    watch_folder = cfg.get("watch_folder", "/Users/risanggalih/Downloads/penjualan")
    print(f"👀 Folder Watcher aktif memantau: {watch_folder}")
    print("Setiap kali Anda menaruh atau men-download file .xlsx Shopee ke folder tersebut, data akan langsung diproses otomatis.")
    print("Tekan Ctrl+C untuk berhenti.")

    while True:
        try:
            res = sync_watch_folder()
            if res.get("status") == "success" and res.get("processed"):
                for item in res["processed"]:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] File baru diproses: {item['file']} (+{item['inserted']} baru, {item['updated']} diperbarui)")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nWatcher dihentikan.")
            break
        except Exception as e:
            print(f"Error watcher: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
