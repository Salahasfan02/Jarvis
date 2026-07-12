"""Exact text extraction using Apple's Vision framework (VNRecognizeTextRequest).

This is the same OCR engine behind macOS Live Text — far more precise for
reading screen text than describing images with a multimodal LLM.
"""
from __future__ import annotations

import asyncio
from pathlib import Path


def _recognize(path: str) -> list[str]:
    import Quartz
    import Vision
    from Foundation import NSURL

    url = NSURL.fileURLWithPath_(path)
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if source is None:
        raise RuntimeError("could not open image")
    cg_image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if cg_image is None:
        raise RuntimeError("could not decode image")

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision request failed: {error}")

    lines: list[str] = []
    for observation in request.results() or []:
        candidate = observation.topCandidates_(1)
        if candidate and len(candidate) > 0:
            lines.append(str(candidate[0].string()))
    return lines


async def ocr_file(path: str | Path) -> str:
    """OCR an image file, returning the recognized lines joined by newlines."""
    lines = await asyncio.to_thread(_recognize, str(path))
    return "\n".join(lines)
