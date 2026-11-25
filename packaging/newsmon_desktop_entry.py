"""PyInstaller entry point: the frozen executable runs newsmon.desktop.main()."""
import multiprocessing
import sys

from newsmon.desktop import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
