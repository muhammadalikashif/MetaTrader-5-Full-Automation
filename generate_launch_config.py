"""
generate_launch_config.py

Writes a launch config INI for the terminal64.exe /config parameter.
Credentials from env vars (MT5_LOGIN, MT5_PASSWORD, MT5_SERVER) or
fallback to values already in the codebase.

Output: D:\\MT5\\config\\launch_autotrade1.ini
"""

import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FALLBACK_LOGIN = 5051817950
FALLBACK_PASSWORD = "7gAuQw-g"
FALLBACK_SERVER = "MetaQuotes-Demo"

INI_TEMPLATE = """[Common]
Login={login}
Server={server}
Password={password}

[Charts]
ProfileLast={profile_name}

[Experts]
AllowLiveTrading=1
AllowDllImport=0
Enabled=1
"""

DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "config", "launch_autotrade1.ini")


def generate(
    login: str,
    password: str,
    server: str,
    profile_name: str = "AutoTrade1",
    out_path: str = DEFAULT_OUTPUT,
) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    content = INI_TEMPLATE.format(
        login=login,
        server=server,
        password=password,
        profile_name=profile_name,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return out_path


def load_credentials() -> dict:
    login = os.environ.get("MT5_LOGIN") or str(FALLBACK_LOGIN)
    password = os.environ.get("MT5_PASSWORD") or FALLBACK_PASSWORD
    server = os.environ.get("MT5_SERVER") or FALLBACK_SERVER
    return {"login": login, "password": password, "server": server}


if __name__ == "__main__":
    creds = load_credentials()
    path = generate(**creds)
    print(f"Launch config written to: {path}")
