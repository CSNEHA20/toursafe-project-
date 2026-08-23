import urllib.request
import re

html_url = "http://localhost:8081"
print(f"Fetching {html_url}...")
with urllib.request.urlopen(html_url) as res:
    html = res.read().decode("utf-8")
    print(f"HTML Status: {res.status}")
    scripts = re.findall(r'src="([^"]+)"', html)
    print("Found scripts:", scripts)
    for s in scripts:
        script_url = s if s.startswith("http") else f"http://localhost:8081{s}"
        print(f"Fetching bundle: {script_url}...")
        with urllib.request.urlopen(script_url) as s_res:
            data = s_res.read()
            print(f"Bundle {script_url} -> Status: {s_res.status}, Size: {len(data)} bytes")

print("Dev server successfully served web application bundle!")
