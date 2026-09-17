"""
Playwright-based crawler and Canvas interceptor for Pixiv Comic Store (PUBLUS Reader).
"""
import asyncio
import re
from typing import Dict, List, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, Response

from core.coordinate_map import SliceCoord, PageMapping


class PixivComicFetcher:
    """
    Automates browsing Pixiv Comic Store viewer using Playwright,
    intercepting scrambled image files and Canvas tile draw calls.
    """

    def __init__(
        self,
        headless: bool = True,
        flip_delay: float = 1.0,
        timeout: int = 60000,
        proxy: Optional[str] = None,
        cookies_path: Optional[str] = None
    ):
        self.headless = headless
        self.flip_delay = flip_delay
        self.timeout = timeout
        self.proxy = proxy
        self.cookies_path = cookies_path

    def normalize_url(self, target: str) -> str:
        """Converts a cid or full URL to the viewer URL."""
        if target.startswith("http://") or target.startswith("https://"):
            return target
        return f"https://comic-store-viewer.pixiv.net/static/viewer?cid={target}"

    async def fetch(self, target_url_or_cid: str, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """
        Loads the viewer, clicks through all pages, and collects all images and slice mappings.
        """
        url = self.normalize_url(target_url_or_cid)
        cid_match = re.search(r"cid=([^&]+)", url)
        cid = cid_match.group(1) if cid_match else "comic"

        comic_title = f"Comic_{cid}"
        scrambled_images: Dict[str, bytes] = {}

        launch_args = {}
        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=self.headless,
                **launch_args
            )
            context = await browser.new_context()

            # Load cookies if provided (yt-dlp / Netscape cookies.txt format)
            if self.cookies_path:
                from utils.cookies import parse_cookie_file
                try:
                    cookies = parse_cookie_file(self.cookies_path)
                    await context.add_cookies(cookies)
                    print(f"[Fetcher] Successfully loaded {len(cookies)} cookies from '{self.cookies_path}'")
                except Exception as e:
                    print(f"[Warning] Failed to load cookies from '{self.cookies_path}': {e}")

            page: Page = await context.new_page()

            # Intercept API responses and scrambled images
            async def on_response(response: Response):
                nonlocal comic_title
                resp_url = response.url

                # Intercept comic title
                if "/api/c?cid=" in resp_url and response.status == 200:
                    try:
                        data = await response.json()
                        if "cti" in data and data["cti"]:
                            comic_title = data["cti"].strip()
                    except Exception:
                        pass

                # Intercept scrambled image files
                if ("/xhtml/" in resp_url or "/product/brws/" in resp_url) and any(
                    ext in resp_url.lower() for ext in [".jpeg", ".jpg", ".png"]
                ):
                    clean_key = resp_url.split("?")[0].split("/xhtml/")[-1]
                    try:
                        body = await response.body()
                        scrambled_images[clean_key] = body
                    except Exception:
                        pass

            page.on("response", on_response)

            # Inject Canvas hook before any script executes
            await page.add_init_script("""
                window.__capturedPages = {};
                const origDrawImage = CanvasRenderingContext2D.prototype.drawImage;
                CanvasRenderingContext2D.prototype.drawImage = function(...args) {
                    let img = args[0];
                    if (img && img.src && (img.src.includes('.jpeg') || img.src.includes('.jpg') || img.src.includes('.png'))) {
                        let cleanUrl = img.src.split('?')[0];
                        let pageKey = cleanUrl.split('/xhtml/')[1] || cleanUrl;

                        if (!window.__capturedPages[pageKey]) {
                            window.__capturedPages[pageKey] = {
                                cleanUrl: cleanUrl,
                                canvasWidth: this.canvas.width,
                                canvasHeight: this.canvas.height,
                                imgWidth: img.naturalWidth || img.width,
                                imgHeight: img.naturalHeight || img.height,
                                slices: []
                            };
                        }
                        if (args.length >= 9) {
                            window.__capturedPages[pageKey].slices.push({
                                sx: Math.round(args[1]),
                                sy: Math.round(args[2]),
                                sw: Math.round(args[3]),
                                sh: Math.round(args[4]),
                                dx: Math.round(args[5]),
                                dy: Math.round(args[6]),
                                dw: Math.round(args[7]),
                                dh: Math.round(args[8])
                            });
                        }
                    }
                    return origDrawImage.apply(this, args);
                };
            """)

            print(f"[Fetcher] Navigating to {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            # Initial wait for viewer and first page (cover) to render
            print("[Fetcher] Waiting for initial page rendering...")
            try:
                await page.wait_for_function(
                    "() => typeof window.__capturedPages === 'object' && Object.keys(window.__capturedPages).length > 0",
                    timeout=15000
                )
            except Exception:
                await asyncio.sleep(4)
            print(f"[Fetcher] Viewer loaded. Title: '{comic_title}'")

            idle_flips = 0
            last_count = 0
            step = 0
            max_steps = 60 if max_pages is None else max_pages * 2

            # Tap on the left side to turn pages in RTL Japanese manga
            viewport_size = page.viewport_size or {"width": 1280, "height": 720}
            click_x = int(viewport_size["width"] * 0.1)
            click_y = int(viewport_size["height"] * 0.5)

            while step < max_steps:
                curr_pages = await page.evaluate("() => Object.keys(window.__capturedPages).length")
                if curr_pages > last_count:
                    idle_flips = 0
                    last_count = curr_pages
                    print(f"[Fetcher] Step {step}: Captured {curr_pages} pages so far...")
                else:
                    if curr_pages > 0:
                        idle_flips += 1

                # If no new pages after 4 consecutive clicks, we reached the end of the comic
                if curr_pages > 0 and idle_flips >= 4:
                    print(f"[Fetcher] No new pages after {idle_flips} consecutive clicks. Reached end of book.")
                    break

                if max_pages and curr_pages >= max_pages:
                    print(f"[Fetcher] Reached requested max pages: {max_pages}")
                    break

                # Click left side to advance page
                await page.mouse.click(click_x, click_y)
                await asyncio.sleep(self.flip_delay)
                step += 1

            # Short wait for any final network / canvas rendering
            await asyncio.sleep(2)

            captured_metadata = await page.evaluate("() => window.__capturedPages")
            await browser.close()

        print(f"[Fetcher] Crawling complete. Total metadata pages: {len(captured_metadata)}, total raw images: {len(scrambled_images)}")

        # Assemble result list
        pages_result = []
        for page_key, meta in captured_metadata.items():
            img_bytes = scrambled_images.get(page_key)
            if not img_bytes:
                # Fuzzy filename match
                fn = page_key.split("/")[-1]
                for k, v in scrambled_images.items():
                    if k.endswith(fn):
                        img_bytes = v
                        break

            if not img_bytes:
                print(f"[Warning] Raw image data missing for page: {page_key}")
                continue

            slices = [SliceCoord.from_dict(s) for s in meta["slices"]]
            page_mapping = PageMapping(
                canvas_size=(meta["canvasWidth"], meta["canvasHeight"]),
                scrambled_size=(meta["imgWidth"], meta["imgHeight"]),
                slices=slices
            )

            pages_result.append({
                "page_key": page_key,
                "mapping": page_mapping,
                "image_bytes": img_bytes,
            })

        # Sort pages in natural order: cover, p-001, p-002, ...
        def sort_key(item):
            key = item["page_key"]
            if "cover" in key:
                return -1
            num_match = re.search(r"(\d+)", key)
            return int(num_match.group(1)) if num_match else 9999

        pages_result.sort(key=sort_key)

        return {
            "title": comic_title,
            "cid": cid,
            "pages": pages_result
        }
