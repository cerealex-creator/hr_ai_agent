"""Extract candidate portrait from PDF resume (best effort, optional deps)."""

from __future__ import annotations

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

MIN_SIZE = 100
ASPECT_MIN = 0.7
ASPECT_MAX = 1.4
SCAN_DPI = 150
CROP_PAD = 0.20


def _aspect_ok(width: int, height: int) -> bool:
    if width < MIN_SIZE or height < MIN_SIZE:
        return False
    ratio = width / height if height else 0.0
    return ASPECT_MIN <= ratio <= ASPECT_MAX


def _load_cv2():
    import cv2  # noqa: PLC0415

    return cv2


def _decode_image(data: bytes):
    import numpy as np  # noqa: PLC0415

    cv2 = _load_cv2()
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _face_cascade():
    cv2 = _load_cv2()
    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(path)
    return cascade if not cascade.empty() else None


def _detect_faces(gray):
    cascade = _face_cascade()
    if cascade is None:
        return ()
    cv2 = _load_cv2()
    return cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(MIN_SIZE, MIN_SIZE),
    )


def _has_face(image_bgr) -> bool:
    cv2 = _load_cv2()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    faces = _detect_faces(gray)
    return len(faces) > 0


def _encode_jpeg(image_bgr, *, quality: int = 85) -> bytes | None:
    cv2 = _load_cv2()
    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    return buf.tobytes()


def _crop_largest_face(image_bgr) -> bytes | None:
    cv2 = _load_cv2()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    faces = _detect_faces(gray)
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    ih, iw = image_bgr.shape[:2]
    pad_w = int(w * CROP_PAD)
    pad_h = int(h * CROP_PAD)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(iw, x + w + pad_w)
    y2 = min(ih, y + h + pad_h)
    crop = image_bgr[y1:y2, x1:x2]
    return _encode_jpeg(crop)


def _jpeg_from_image_bytes(data: bytes) -> bytes | None:
    image = _decode_image(data)
    if image is None:
        return None
    height, width = image.shape[:2]
    if not _has_face(image):
        return None
    if _aspect_ok(width, height):
        return _encode_jpeg(image)
    return _crop_largest_face(image)


def _embedded_images_first_page(page) -> list[bytes]:
    out: list[bytes] = []
    doc = page.parent
    for info in page.get_images(full=True):
        xref = int(info[0])
        try:
            extracted = doc.extract_image(xref)
        except Exception:  # noqa: BLE001
            continue
        blob = extracted.get("image") if isinstance(extracted, dict) else None
        if blob:
            out.append(blob)
    return out


def _render_first_page(page) -> bytes | None:
    try:
        import fitz  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        cv2 = _load_cv2()
        scale = SCAN_DPI / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        channels = pix.n
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, channels)
        if channels == 4:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif channels == 3:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            return None
        return _crop_largest_face(bgr)
    except Exception:  # noqa: BLE001
        logger.debug("PDF page render fallback failed", exc_info=True)
        return None


def extract_photo_from_pdf_bytes(content: bytes) -> bytes | None:
    """Return JPEG bytes with a detected face, or None."""
    if not content or not content.lstrip().startswith(b"%PDF"):
        return None
    try:
        import fitz  # noqa: PLC0415
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — skip photo extraction")
        return None
    try:
        import cv2  # noqa: F401, PLC0415
    except ImportError:
        logger.warning("opencv-python not installed — skip photo extraction")
        return None

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:  # noqa: BLE001
        logger.debug("Cannot open PDF for photo extract", exc_info=True)
        return None

    try:
        if doc.page_count < 1:
            return None
        page = doc.load_page(0)
        for blob in _embedded_images_first_page(page):
            jpeg = _jpeg_from_image_bytes(blob)
            if jpeg:
                return jpeg
        return _render_first_page(page)
    finally:
        doc.close()
