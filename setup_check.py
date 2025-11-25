import os
import shutil
import sys


def check():
    print("Checking environment...")
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required.")
        return

    if not shutil.which("ollama"):
        print("❌ Ollama not found. Please install it.")
        return

    print("✅ Environment looks good. Pulling model (this might take a while)...")

    os.system("ollama pull qwen3:8b")
    print("✅ Ready! Run 'python main.py'")


if __name__ == "__main__":
    check()
