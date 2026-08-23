import os
import re

PATTERNS = [
    re.compile(r'(?i)(password|secret|api_key|private_key)\s*[:=]\s*["\']([^"\']{12,})["\']'),
    re.compile(r'mongodb(\+srv)?:\/\/[^\s"\']+:[^\s"\']+@'),
    re.compile(r'postgres(ql)?:\/\/[^\s"\']+:[^\s"\']+@'),
    re.compile(r'redis:\/\/[^\s"\']+:[^\s"\']+@'),
]

IGNORE_KEYWORDS = [
    "example", "placeholder", "your-", "change-", "default", 
    "process.env", "os.environ", "Field(", "localhost", 
    "test", "fake", "mock", "dummy"
]

findings = []
for root, dirs, files in os.walk("."):
    if any(p in root for p in ["node_modules", ".git", "dist", ".expo", "__pycache__", ".pytest_cache"]):
        continue
    for file in files:
        if file.endswith((".py", ".ts", ".tsx", ".json", ".yml", ".yaml", ".env", ".example")):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        for pattern in PATTERNS:
                            m = pattern.search(line)
                            if m:
                                matched_str = m.group(0)
                                if not any(kw in matched_str.lower() or kw in line.lower() for kw in IGNORE_KEYWORDS):
                                    findings.append((filepath, line_num, line.strip()))
            except Exception:
                pass

print(f"Potential hardcoded credentials found: {len(findings)}")
for fp, ln, txt in findings:
    print(f"  {fp}:{ln} -> {txt[:100]}")
