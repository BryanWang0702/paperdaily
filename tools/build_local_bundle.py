from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ROOT_FILES = [
    "VERSION",
    "standalone_version.json",
    "config.yaml",
    "config.template.yaml",
    "requirements.txt",
    "local_app.py",
    "api_token.example.txt",
    "START_PAPERDAILY_WINDOWS.bat",
    "START_PAPERDAILY_MAC_LINUX.sh",
]


def iter_files():
    for relative in ROOT_FILES:
        path = ROOT / relative
        if path.exists():
            yield path, Path(relative)

    for path in sorted((ROOT / "src").rglob("*.py")):
        yield path, path.relative_to(ROOT)

    for path in sorted((ROOT / "topics").glob("*.yaml")):
        yield path, path.relative_to(ROOT)

    for name in ("index.html", "day.html", "app.js", "day.js", "style.css", "layout.css", "theme.js", "topics.js"):
        path = ROOT / "site" / name
        if path.exists():
            yield path, path.relative_to(ROOT)

    docs = [
        ("LOCAL_VERSION.md", "README_LOCAL.md"),
        ("LOCAL_VERSION.zh-CN.md", "README_LOCAL.zh-CN.md"),
    ]
    for source_name, output_name in docs:
        path = ROOT / "docs" / source_name
        if path.exists():
            yield path, Path(output_name)


def build(output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, relative in iter_files():
            archive.write(source, Path("PaperDaily-local") / relative)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Python-based PaperDaily local-edition ZIP")
    parser.add_argument(
        "--output",
        default="dist/PaperDaily-local.zip",
        help="Output ZIP path",
    )
    args = parser.parse_args()
    path = build(ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output))
    print(path)


if __name__ == "__main__":
    main()
