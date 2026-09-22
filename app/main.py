from __future__ import annotations

import argparse

from app.services.demo_runner import DemoRunner
from app.ui.main_window import run_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Engineering Product Analyzer demo")
    parser.add_argument("--demo", action="store_true", help="Run demo pipeline and write outputs without launching the GUI.")
    args = parser.parse_args()
    if args.demo:
        result, _, _ = DemoRunner().run()
        print("Demo analysis complete.")
        for name, path in result.output_files.items():
            print(f"{name}: {path}")
        return 0
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())

