#!/usr/bin/env python3
"""Entry point for the R48 controller GUI."""
from r48.ui import R48Application


def main() -> None:
    R48Application().mainloop()


if __name__ == "__main__":
    main()