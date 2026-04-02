import subprocess
import sys
import os
import time
import socket
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("launcher")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

SERVICES = [
    {"name": "Search Service", "script": os.path.join("services", "search_service.py"), "port": config.SEARCH_SERVICE_PORT},
    {"name": "LLM Service",    "script": os.path.join("services", "llm_service.py"),    "port": config.LLM_SERVICE_PORT},
    {"name": "Web Client",     "script": os.path.join("services", "web_client.py"),     "port": config.WEB_CLIENT_PORT},
]

MAX_RESTARTS = 5


def is_port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def free_port(port):
    if is_port_free(port):
        return True
    log.warning(f"Порт {port} занят, пытаемся освободить...")
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=5)
        time.sleep(0.5)
        if is_port_free(port):
            log.info(f"Порт {port} освобождён")
            return True
        log.error(f"Не удалось освободить порт {port}")
        return False
    except Exception as e:
        log.error(f"Ошибка при освобождении порта {port}: {e}")
        return False


def main():
    print("=" * 60)
    print("  Справочная система по внутренним документам")
    print("  Запуск сервисов...")
    print("=" * 60)

    for svc in SERVICES:
        if not free_port(svc["port"]):
            log.error(f"Порт {svc['port']} для {svc['name']} занят. Выход.")
            sys.exit(1)

    processes = []
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for svc in SERVICES:
        script_path = os.path.join(base_dir, svc["script"])
        log.info(f"Запуск {svc['name']} (порт {svc['port']})...")

        proc = subprocess.Popen(
            [sys.executable, script_path], cwd=base_dir, stdout=sys.stdout, stderr=sys.stderr,
        )
        processes.append((svc["name"], proc))
        time.sleep(1.5)

        if proc.poll() is not None:
            log.error(f"{svc['name']} не запустился (код: {proc.returncode})")
            for name, p in processes:
                p.terminate()
            sys.exit(1)
        log.info(f"{svc['name']} запущен (PID: {proc.pid})")

    print(f"\n  Все сервисы запущены: http://localhost:{SERVICES[-1]['port']}")
    print("  Ctrl+C для остановки\n")

    restart_counts = {svc["name"]: 0 for svc in SERVICES}

    try:
        while True:
            for i, (name, proc) in enumerate(processes):
                if proc.poll() is not None:
                    if restart_counts[name] >= MAX_RESTARTS:
                        log.error(f"{name} исчерпал лимит перезапусков ({MAX_RESTARTS})")
                        continue
                    restart_counts[name] += 1
                    log.warning(f"{name} упал (код {proc.returncode}), перезапуск {restart_counts[name]}/{MAX_RESTARTS}...")
                    svc = SERVICES[i]
                    new_proc = subprocess.Popen(
                        [sys.executable, os.path.join(base_dir, svc["script"])],
                        cwd=base_dir, stdout=sys.stdout, stderr=sys.stderr,
                    )
                    processes[i] = (name, new_proc)
                    log.info(f"{name} перезапущен (PID: {new_proc.pid})")
            time.sleep(2)
    except KeyboardInterrupt:
        log.info("Остановка...")
        for name, proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for name, proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Все сервисы остановлены.")


if __name__ == "__main__":
    main()
