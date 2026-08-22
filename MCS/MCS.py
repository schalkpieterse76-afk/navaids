"""MCS CVOR RMS – simple browser launcher."""

import os
import sys
import webbrowser

_HERE = os.path.dirname(os.path.abspath(__file__))
_HTML = os.path.join(_HERE, "MCS_CVOR_RMS.html")


def main():
    if not os.path.isfile(_HTML):
        print(f"[MCS] Cannot find {_HTML}")
        sys.exit(1)
    url = f"file:///{_HTML.replace(os.sep, '/')}"
    print(f"[MCS] Opening {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    main()
