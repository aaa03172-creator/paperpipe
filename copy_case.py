
import shutil
import os

source = "/Users/jangseongjin/Library/CloudStorage/OneDrive-개인/ai논문에이전트/사례 조사/PaperPipe_cases_only_checked_v3.docx"
dest = "PaperPipe_cases.docx"

try:
    shutil.copy2(source, dest)
    print(f"✅ Copied to {dest}")
except Exception as e:
    print(f"❌ Copy failed: {e}")
