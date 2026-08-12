"""One-shot script: extract photos from PDF resumes for all candidates missing photo_url."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.db import models
from app.services.pdf_extract import download_url_bytes
from app.services.candidate_photo import try_attach_candidate_photo


def main():
    db = SessionLocal()
    try:
        candidates = db.query(models.Candidate).all()
        total = len(candidates)
        skipped = 0
        success = 0
        failed = 0

        for i, cand in enumerate(candidates, 1):
            payload = dict(cand.payload or {})
            existing_photo = str(payload.get("photo_url") or "").strip()
            if existing_photo:
                skipped += 1
                continue

            resume_link = str(payload.get("resume_link") or "").strip()
            if not resume_link:
                skipped += 1
                continue

            print(f"[{i}/{total}] {cand.name or cand.id} — downloading...", end=" ", flush=True)
            try:
                blob = download_url_bytes(resume_link)
                if not blob or not blob.lstrip().startswith(b"%PDF"):
                    print("not a PDF, skip")
                    skipped += 1
                    continue
                attached = try_attach_candidate_photo(db, cand, pdf_bytes=blob)
                if attached:
                    print("OK ✓")
                    success += 1
                else:
                    print("no face detected")
                    failed += 1
            except Exception as e:
                print(f"error: {e}")
                failed += 1

        print(f"\nDone. Total: {total}, Photos added: {success}, No face/skip: {skipped + failed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
