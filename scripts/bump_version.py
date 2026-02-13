import re
import sys
from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parents[1] / "version.py"


def _read_version_text() -> str:
    return VERSION_FILE.read_text(encoding="utf-8")


def _write_version_text(text: str) -> None:
    VERSION_FILE.write_text(text, encoding="utf-8")


def _parse_version(text: str) -> tuple[int, int, int]:
    m = re.search(r"APP_VERSION\s*=\s*\"v(\d+)\.(\d+)\.(\d{4})\"", text)
    if not m:
        raise SystemExit(f"Não foi possível ler APP_VERSION em {VERSION_FILE}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _format_version(major: int, minor: int, build: int) -> str:
    return f"v{major}.{minor}.{build:04d}"


def bump(kind: str) -> str:
    text = _read_version_text()
    major, minor, build = _parse_version(text)

    kind_norm = kind.strip().lower()
    if kind_norm in {"normal", "n"}:
        build += 1
    elif kind_norm in {"media", "m", "média"}:
        minor += 1
        build = 0
    elif kind_norm in {"avancada", "a", "avançada"}:
        major += 1
        minor = 0
        build = 0
    else:
        raise SystemExit("Uso: python scripts/bump_version.py normal|media|avancada")

    new_version = _format_version(major, minor, build)
    new_text = re.sub(
        r"APP_VERSION\s*=\s*\"v\d+\.\d+\.\d{4}\"",
        f'APP_VERSION = "{new_version}"',
        text,
        count=1,
    )

    _write_version_text(new_text)
    return new_version


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: python scripts/bump_version.py normal|media|avancada")
        return 2

    new_version = bump(argv[1])
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
