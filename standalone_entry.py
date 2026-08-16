from __future__ import annotations

import sys

from local_app import _app_version, main


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(f"PaperDaily {_app_version()}")
    else:
        main()
