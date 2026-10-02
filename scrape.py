"""อ่านลิงค์ที่รอดำเนินการจาก Apps Script -> เปิดหน้า Shopee ด้วย Chromium -> ส่งชื่อ+รูปกลับ"""
import os, re, json, base64, requests
from playwright.sync_api import sync_playwright

EXEC = os.environ["EXEC_URL"]
TOKEN = os.environ.get("TOKEN", "")
os.makedirs("shots", exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

JS_IMGS = """() => {
  const o = [];
  const m = document.querySelector('meta[property="og:image"]'); if (m && m.content) o.push(m.content);
  document.querySelectorAll('img').forEach(i => {
    const s = i.currentSrc || i.src;
    if (s && s.includes('susercontent.com/file/')) o.push(s);
  });
  return o;
}"""


def get_pending():
    r = requests.get(EXEC, params={"action": "pending", "token": TOKEN}, timeout=90)
    r.raise_for_status()
    return r.json()


def save(payload):
    payload["token"] = TOKEN
    r = requests.post(EXEC, data=json.dumps(payload),
                      headers={"Content-Type": "text/plain"}, timeout=300)
    print("  save ->", r.status_code, r.text[:120])


def clean(u):
    return re.sub(r"(@resize.*|_tn)$", "", u)


def scrape(ctx, link, tag):
    page = ctx.new_page()
    try:
        page.goto(link, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("h1", timeout=25000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        url = page.url
        name = (page.evaluate("() => (document.querySelector('h1')||{}).innerText || ''") or "").strip()
        if not name:
            name = (page.title() or "").split("|")[0].strip()
        if (not name or re.match(r"(?i)\s*shopee", name)
                or any(k in url for k in ("verify", "login", "captcha"))):
            page.screenshot(path=f"shots/{tag}.png")
            raise RuntimeError("ถูกบล็อกหรือต้องยืนยันตัวตน: " + url[:90])

        urls, seen = [], set()
        for u in page.evaluate(JS_IMGS):
            c = clean(u)
            if c not in seen:
                seen.add(c)
                urls.append(c)
        images = []
        for u in urls[:3]:
            resp = ctx.request.get(u, timeout=60000)
            if resp.ok:
                images.append({"b64": base64.b64encode(resp.body()).decode(),
                               "mime": resp.headers.get("content-type", "image/jpeg")})
        page.screenshot(path=f"shots/{tag}.png")
        return name, images
    finally:
        page.close()


def main():
    items = get_pending()
    print("pending:", len(items))
    if not items:
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="th-TH", timezone_id="Asia/Bangkok",
                                  viewport={"width": 1366, "height": 900})
        for it in items:
            print("row", it["row"], it["link"])
            try:
                name, images = scrape(ctx, it["link"], f"row{it['row']}")
                save({"row": it["row"], "name": name, "images": images})
            except Exception as e:
                print("  error:", e)
                save({"row": it["row"], "error": str(e)[:200]})
        browser.close()


if __name__ == "__main__":
    main()
