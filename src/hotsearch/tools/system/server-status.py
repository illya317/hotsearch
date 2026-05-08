#!/usr/bin/env python3
"""Server status report - daily check at 9:00 AM"""
import subprocess, sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else f"Error"
    except:
        return "Error"

def get_disk():
    out = run_cmd("df -h / | tail -1")
    p = out.split()
    return f"{p[4]} 已用, 剩 {p[3]}" if len(p) >= 5 else "N/A"

def get_mem():
    out = run_cmd("free -h | grep Mem")
    p = out.split()
    return f"用 {p[2]}, 剩 {p[3]}" if len(p) >= 4 else "N/A"

def get_load():
    out = run_cmd("cat /proc/loadavg")
    return out.split()[:3] if out else ["?", "?", "?"]

def get_ip():
    out = run_cmd("curl -s icanhazip.com 2>/dev/null || curl -s ifconfig.me 2>/dev/null")
    return out if out and "Error" not in out else "unknown"

def main():
    disk = get_disk()
    mem = get_mem()
    load = get_load()
    ip = get_ip()
    report = f"""📊 服务器日报 ({datetime.now().strftime('%m-%d %H:%M')})

💾 磁盘: {disk}
🧠 内存: {mem}
🔧 负载: {load[0]} / {load[1]} / {load[2]}

💡 详情: ssh root@{ip}"""
    print(report)

if __name__ == "__main__":
    main()
