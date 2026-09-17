"""
Main entry point for Pixiv Comic Store (PUBLUS Reader) Downloader & Descrambler.
"""
import argparse
import asyncio
import json
import os
import sys
from typing import List
from PIL import Image

# Reconfigure stdout/stderr for proper UTF-8 handling on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.puzzle import reassemble_image
from crawler.playwright_fetcher import PixivComicFetcher
from utils.exporter import (
    sanitize_filename,
    save_pages_as_images,
    export_to_pdf,
    export_to_cbz,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pixiv Comic Store (PUBLUS Reader) Downloader & Puzzle Reassembly Tool (By ZGQ Inc.)"
    )
    parser.add_argument(
        "target",
        help="Pixiv comic viewer URL or cid (e.g. gkagktexy or https://comic-store-viewer.pixiv.net/static/viewer?cid=gkagktexy)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="./output",
        help="Base directory to save output comics (default: ./output)",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["cbz", "png", "jpg", "pdf", "all"],
        default="cbz",
        help="Output format: cbz (default, prioritized for manga), png, jpg, pdf, or all",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (useful for debugging)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum pages to download (default: all)",
    )
    parser.add_argument(
        "--flip-delay",
        type=float,
        default=1.0,
        help="Delay in seconds between page flips (default: 1.0)",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help="Path to cookies.txt file in Netscape / curl format (similar to yt-dlp --cookies)",
    )
    parser.add_argument(
        "--save-scrambled",
        action="store_true",
        help="Also save raw scrambled images before reconstruction",
    )
    parser.add_argument(
        "--save-coords",
        action="store_true",
        help="Save coordinate mapping tables as JSON",
    )
    return parser.parse_args()


async def main_async():
    args = parse_args()

    print("=" * 60)
    print(" Pixiv Comic Store (PUBLUS Reader) Downloader & Descrambler")
    print(" Copyright (c) 2026 ZGQ Inc. - MIT License")
    print("=" * 60)
    print(f" Target: {args.target}")
    print(f" Primary Format: {args.format.upper()} (Default: CBZ)")
    print(f" Output Directory: {args.output_dir}")
    if args.cookies:
        print(f" Cookies File: {args.cookies}")
    print(f" Headless: {not args.no_headless}")
    print("=" * 60)

    fetcher = PixivComicFetcher(
        headless=not args.no_headless,
        flip_delay=args.flip_delay,
        cookies_path=args.cookies,
    )

    try:
        data = await fetcher.fetch(args.target, max_pages=args.max_pages)
    except Exception as e:
        print(f"\n[Error] Failed during fetch: {e}")
        sys.exit(1)

    title = data["title"]
    pages = data["pages"]

    if not pages:
        print("\n[Error] No pages were captured. Please check the URL/cid and network.")
        sys.exit(1)

    safe_title = sanitize_filename(title)
    comic_folder = os.path.join(args.output_dir, safe_title)
    os.makedirs(comic_folder, exist_ok=True)

    print(f"\n[Reassembler] Processing {len(pages)} captured pages for: '{title}'...")

    reassembled_images: List[Image.Image] = []
    all_mappings = {}

    for idx, page_info in enumerate(pages, start=1):
        mapping = page_info["mapping"]
        img_bytes = page_info["image_bytes"]
        key = page_info["page_key"]

        # Reassemble using PIL puzzle engine
        clean_img = reassemble_image(img_bytes, mapping)
        reassembled_images.append(clean_img)

        print(f"  [{idx:02d}/{len(pages):02d}] Reassembled {key}: Scrambled {mapping.scrambled_size} -> Clean {clean_img.size}")

        if args.save_scrambled:
            scrambled_dir = os.path.join(comic_folder, "scrambled")
            os.makedirs(scrambled_dir, exist_ok=True)
            with open(os.path.join(scrambled_dir, f"{idx:03d}_{os.path.basename(key)}"), "wb") as f:
                f.write(img_bytes)

        if args.save_coords:
            all_mappings[key] = mapping.to_dict()

    if args.save_coords and all_mappings:
        coords_path = os.path.join(comic_folder, "coordinate_mappings.json")
        with open(coords_path, "w", encoding="utf-8") as f:
            json.dump(all_mappings, f, indent=2)
        print(f"[Info] Coordinate mappings saved to {coords_path}")

    # Export (CBZ prioritized, followed by PNG/JPG/PDF)
    print("\n[Exporter] Exporting restored comic...")
    fmt = args.format.lower()

    if fmt in ["cbz", "all"]:
        cbz_file = os.path.join(comic_folder, f"{safe_title}.cbz")
        export_to_cbz(reassembled_images, cbz_file)
        print(f"  -> [Primary] Exported CBZ archive: {cbz_file}")

    if fmt in ["png", "all"]:
        png_paths = save_pages_as_images(reassembled_images, comic_folder, img_format="PNG")
        print(f"  -> Saved {len(png_paths)} individual PNG images to: {comic_folder}")

    if fmt == "jpg":
        jpg_paths = save_pages_as_images(reassembled_images, comic_folder, img_format="JPEG")
        print(f"  -> Saved {len(jpg_paths)} individual JPG images to: {comic_folder}")

    if fmt in ["pdf", "all"]:
        pdf_file = os.path.join(comic_folder, f"{safe_title}.pdf")
        export_to_pdf(reassembled_images, pdf_file)
        print(f"  -> Exported PDF document: {pdf_file}")

    print("\n" + "=" * 60)
    print(f" Download & Reconstruction Complete!")
    print(f" Comic Title : {title}")
    print(f" Total Pages : {len(reassembled_images)}")
    print(f" Output Path : {os.path.abspath(comic_folder)}")
    print("=" * 60)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
