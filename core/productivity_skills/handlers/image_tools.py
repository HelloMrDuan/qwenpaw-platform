"""Image toolkit, restoration, background and quality handlers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from ..artifacts import artifact, safe_output_path
from ..capabilities import CapabilityResolver
from ..models import SkillStatus, invalid, result


def _pillow():
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat
    except ImportError:
        return None
    return Image, ImageEnhance, ImageFilter, ImageOps, ImageStat


def _source(request: Mapping[str, Any]) -> Path | None:
    value = request.get("input")
    if not value:
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_file() else None


def _image_artifact(path: Path, operation: str, source: Path) -> dict[str, Any]:
    pillow = _pillow()
    extra: dict[str, Any] = {}
    if pillow:
        Image = pillow[0]
        try:
            with Image.open(path) as image:
                extra.update(width=image.width, height=image.height, format=image.format)
        except Exception:
            with Image.open(source) as image:
                extra.update(width=image.width, height=image.height, format=path.suffix.lstrip(".").upper())
    return artifact(path, operation=operation, source=source, extra=extra)


def _save(image, request, source: Path, operation: str, extension: str | None = None):
    suffix = extension or source.suffix or ".png"
    output = safe_output_path(
        request,
        source=source,
        stem_suffix=operation.replace("_", "-"),
        extension=suffix,
    )
    options: dict[str, Any] = {}
    if request.get("quality") is not None and suffix.lower() in {".jpg", ".jpeg", ".webp"}:
        options["quality"] = max(1, min(100, int(request["quality"])))
    if request.get("dpi") is not None:
        dpi = int(request["dpi"])
        options["dpi"] = (dpi, dpi)
    if image.mode == "RGBA" and suffix.lower() in {".jpg", ".jpeg"}:
        from PIL import Image as PillowImage
        background = PillowImage.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        image = background
    image.save(output, **options)
    return output, _image_artifact(output, operation, source)


def _require_image(request: Mapping[str, Any]):
    pillow = _pillow()
    if pillow is None:
        return None, None, result(
            SkillStatus.DEPENDENCY_MISSING,
            "Pillow is required for this operation",
            error_code="PILLOW_MISSING",
        )
    source = _source(request)
    if source is None:
        return None, None, invalid("input must reference an existing image")
    try:
        image = pillow[0].open(source)
        image.load()
    except Exception as exc:
        return None, None, invalid(f"input is not a readable image: {exc}")
    return pillow, (source, image), None


def _image_toolkit(request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation") or "info").lower()
    if operation in {"duplicates", "duplicate_detection"}:
        paths = [Path(str(item)) for item in request.get("inputs", [])]
        existing = [item for item in paths if item.is_file()]
        groups: dict[str, list[str]] = {}
        for path in existing:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            groups.setdefault(digest, []).append(path.name)
        duplicates = {key: value for key, value in groups.items() if len(value) > 1}
        return result(
            SkillStatus.SUCCESS,
            "Duplicate detection completed",
            data={"files": len(existing), "duplicate_groups": duplicates},
        )
    pillow, loaded, error = _require_image(request)
    if error:
        return error
    assert pillow and loaded
    Image, _ImageEnhance, _ImageFilter, ImageOps, _ImageStat = pillow
    source, image = loaded
    try:
        if operation in {"info", "exif", "hash"}:
            exif = {
                str(key): str(value)
                for key, value in image.getexif().items()
            }
            dpi = image.info.get("dpi")
            return result(
                SkillStatus.SUCCESS,
                "Image inspection completed",
                data={
                    "filename": source.name,
                    "width": image.width,
                    "height": image.height,
                    "format": image.format,
                    "mode": image.mode,
                    "dpi": list(dpi) if isinstance(dpi, tuple) else dpi,
                    "exif": exif,
                    "checksum": hashlib.sha256(source.read_bytes()).hexdigest(),
                },
            )
        if operation == "convert":
            extension = "." + str(request.get("format") or "png").lower().lstrip(".")
            output, item = _save(image, request, source, operation, extension)
        elif operation == "resize":
            width = int(request.get("width") or 0)
            height = int(request.get("height") or 0)
            if width <= 0 and height <= 0:
                return invalid("resize requires width or height")
            if width <= 0:
                width = max(1, round(image.width * height / image.height))
            if height <= 0:
                height = max(1, round(image.height * width / image.width))
            output, item = _save(image.resize((width, height), Image.Resampling.LANCZOS), request, source, operation)
        elif operation == "crop":
            box = request.get("box")
            if not isinstance(box, list) or len(box) != 4:
                return invalid("crop requires box=[left,top,right,bottom]")
            coords = tuple(int(value) for value in box)
            if coords[0] < 0 or coords[1] < 0 or coords[2] > image.width or coords[3] > image.height or coords[0] >= coords[2] or coords[1] >= coords[3]:
                return invalid("crop box is outside the image")
            output, item = _save(image.crop(coords), request, source, operation)
        elif operation == "rotate":
            output, item = _save(image.rotate(float(request.get("angle", 90)), expand=True), request, source, operation)
        elif operation == "flip":
            axis = str(request.get("axis") or "horizontal")
            changed = ImageOps.mirror(image) if axis == "horizontal" else ImageOps.flip(image)
            output, item = _save(changed, request, source, operation)
        elif operation in {"compress", "quality", "dpi"}:
            output, item = _save(image, request, source, operation)
        elif operation in {"strip_exif", "remove_exif"}:
            clean = Image.new(image.mode, image.size)
            clean.putdata(list(image.getdata()))
            output, item = _save(clean, request, source, operation)
        elif operation == "alpha":
            changed = image.convert("RGBA")
            alpha = max(0, min(255, int(request.get("alpha", 255))))
            changed.putalpha(alpha)
            output, item = _save(changed, request, source, operation, ".png")
        elif operation == "to_pdf":
            changed = image.convert("RGB")
            output, item = _save(changed, request, source, operation, ".pdf")
        elif operation == "concat":
            inputs = [source] + [Path(str(item)) for item in request.get("inputs", [])]
            images = [Image.open(item).convert("RGBA") for item in inputs if item.is_file()]
            direction = str(request.get("direction") or "vertical")
            if direction == "horizontal":
                canvas = Image.new("RGBA", (sum(i.width for i in images), max(i.height for i in images)), (0, 0, 0, 0))
                offset = 0
                for item_image in images:
                    canvas.paste(item_image, (offset, 0)); offset += item_image.width
            else:
                canvas = Image.new("RGBA", (max(i.width for i in images), sum(i.height for i in images)), (0, 0, 0, 0))
                offset = 0
                for item_image in images:
                    canvas.paste(item_image, (0, offset)); offset += item_image.height
            output, item = _save(canvas, request, source, operation, ".png")
        elif operation == "split":
            rows = max(1, int(request.get("rows", 1)))
            columns = max(1, int(request.get("columns", 1)))
            artifacts = []
            for row in range(rows):
                for column in range(columns):
                    box = (
                        column * image.width // columns,
                        row * image.height // rows,
                        (column + 1) * image.width // columns,
                        (row + 1) * image.height // rows,
                    )
                    split_request = dict(request)
                    split_request["output_dir"] = request.get("output_dir")
                    out = safe_output_path(split_request, source=source, stem_suffix=f"split-{row + 1}-{column + 1}", extension=source.suffix or ".png")
                    image.crop(box).save(out)
                    artifacts.append(_image_artifact(out, operation, source))
            return result(SkillStatus.SUCCESS, "Image split completed", data={"parts": len(artifacts)}, artifacts=artifacts)
        else:
            return result(SkillStatus.UNSUPPORTED, f"Unsupported image-toolkit operation: {operation}", error_code="UNSUPPORTED_OPERATION")
        return result(SkillStatus.SUCCESS, f"Image {operation} completed", data={"output": output.name}, artifacts=[item])
    finally:
        image.close()


def _photo_restoration(request: dict[str, Any]) -> dict[str, Any]:
    pillow, loaded, error = _require_image(request)
    if error:
        return error
    assert pillow and loaded
    Image, ImageEnhance, ImageFilter, ImageOps, ImageStat = pillow
    source, image = loaded
    resolver = CapabilityResolver()
    requested_ai = [
        name for name in ("realesrgan", "gfpgan", "codeformer", "lama")
        if bool(request.get(name))
    ]
    if request.get("colorize"):
        requested_ai.append("colorization")
    capabilities = resolver.resolve_many(("pillow", "opencv", *requested_ai))
    try:
        grayscale = image.convert("L")
        stat = ImageStat.Stat(grayscale)
        assessment = {
            "mean_luminance": round(float(stat.mean[0]), 3),
            "contrast_stddev": round(float(stat.stddev[0]), 3),
            "low_light": stat.mean[0] < 65,
            "low_contrast": stat.stddev[0] < 28,
        }
        if str(request.get("operation") or "pipeline") == "inspect":
            return result(SkillStatus.SUCCESS, "Damage assessment completed", data=assessment, capabilities=capabilities)
        changed = image.convert("RGB")
        changed = changed.filter(ImageFilter.MedianFilter(size=3))
        changed = changed.filter(ImageFilter.UnsharpMask(radius=1.6, percent=135, threshold=3))
        changed = ImageOps.autocontrast(changed, cutoff=1)
        changed = ImageEnhance.Color(changed).enhance(float(request.get("color", 1.08)))
        changed = ImageEnhance.Contrast(changed).enhance(float(request.get("contrast", 1.08)))
        if assessment["low_light"]:
            changed = ImageEnhance.Brightness(changed).enhance(1.18)
        output, item = _save(changed, request, source, "restored")
        comparison = Image.new("RGB", (image.width * 2, image.height), "white")
        comparison.paste(image.convert("RGB"), (0, 0)); comparison.paste(changed, (image.width, 0))
        compare_request = dict(request)
        compare_output, compare_item = _save(comparison, compare_request, source, "restoration-comparison", ".jpg")
        # Discovery alone is not execution: model stages require an injected
        # Runtime adapter, which the standalone CLI intentionally does not own.
        missing_ai = list(requested_ai)
        missing_native = ["opencv_scratch_adapter"] if request.get("scratch_repair") else []
        status = SkillStatus.PARTIAL_SUCCESS if missing_ai or missing_native else SkillStatus.SUCCESS
        return result(
            status,
            "Traditional restoration completed" + ("; requested optional stages are unavailable" if missing_ai or missing_native else ""),
            data={"assessment": assessment, "output": output.name, "comparison": compare_output.name, "missing_ai_stages": missing_ai, "missing_native_stages": missing_native},
            artifacts=[item, compare_item],
            capabilities=capabilities,
            error_code="MODEL_RUNTIME_REQUIRED" if missing_ai else "DEPENDENCY_MISSING" if missing_native else None,
        )
    finally:
        image.close()


def _background(request: dict[str, Any]) -> dict[str, Any]:
    pillow, loaded, error = _require_image(request)
    if error:
        return error
    assert pillow and loaded
    Image, _ImageEnhance, ImageFilter, _ImageOps, _ImageStat = pillow
    source, image = loaded
    operation = str(request.get("operation") or "remove_solid")
    resolver = CapabilityResolver()
    capabilities = resolver.resolve_many(("pillow", "opencv", "background_removal"))
    try:
        if operation in {"segment", "alpha_matting"}:
            return result(SkillStatus.MODEL_RUNTIME_REQUIRED, "Complex segmentation requires rembg or another segmentation Runtime", error_code="MODEL_RUNTIME_REQUIRED", capabilities=capabilities)
        rgba = image.convert("RGBA")
        if operation in {"remove_solid", "transparent", "segment", "alpha_matting"}:
            pixels = list(rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata())
            corner = pixels[0][:3]
            threshold = max(0, min(255, int(request.get("threshold", 30))))
            changed_pixels = []
            for red, green, blue, alpha in pixels:
                distance = max(abs(red - corner[0]), abs(green - corner[1]), abs(blue - corner[2]))
                changed_pixels.append((red, green, blue, 0 if distance <= threshold else alpha))
            rgba.putdata(changed_pixels)
            rgba = rgba.filter(ImageFilter.SMOOTH)
            output, item = _save(rgba, request, source, "background-removed", ".png")
        elif operation in {"white", "black", "color", "replace"}:
            color = request.get("color") or ("white" if operation == "white" else "black")
            background = Image.new("RGBA", rgba.size, color)
            background.alpha_composite(rgba)
            output, item = _save(background.convert("RGB"), request, source, "background-replaced", ".jpg")
        elif operation == "blur":
            background = image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=float(request.get("radius", 12))))
            if "A" in rgba.getbands():
                background.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
            output, item = _save(background, request, source, "background-blurred")
        elif operation == "crop_subject":
            bbox = rgba.getchannel("A").getbbox()
            if not bbox:
                return invalid("No non-transparent subject was detected")
            output, item = _save(rgba.crop(bbox), request, source, "subject-cropped", ".png")
        else:
            return result(SkillStatus.UNSUPPORTED, f"Unsupported background operation: {operation}", error_code="UNSUPPORTED_OPERATION")
        return result(SkillStatus.SUCCESS, "Background operation completed", data={"output": output.name}, artifacts=[item], capabilities=capabilities)
    finally:
        image.close()


def _quality(request: dict[str, Any]) -> dict[str, Any]:
    pillow, loaded, error = _require_image(request)
    if error:
        return error
    assert pillow and loaded
    Image, ImageEnhance, ImageFilter, ImageOps, ImageStat = pillow
    source, image = loaded
    resolver = CapabilityResolver()
    capabilities = resolver.resolve_many(("pillow", "opencv", "realesrgan"))
    ai = bool(request.get("ai"))
    if ai:
        image.close()
        return result(SkillStatus.MODEL_RUNTIME_REQUIRED, "AI super-resolution requires an injected Real-ESRGAN Runtime adapter", error_code="MODEL_RUNTIME_REQUIRED", capabilities=capabilities)
    try:
        changed = image.convert("RGB")
        factor = int(request.get("upscale", 1))
        if factor not in {1, 2, 4}:
            return invalid("upscale must be 1, 2 or 4")
        if factor > 1:
            changed = changed.resize((changed.width * factor, changed.height * factor), Image.Resampling.LANCZOS)
        changed = changed.filter(ImageFilter.MedianFilter(size=3))
        changed = changed.filter(ImageFilter.UnsharpMask(radius=1.5, percent=int(request.get("sharpen", 125)), threshold=3))
        changed = ImageEnhance.Contrast(changed).enhance(float(request.get("contrast", 1.05)))
        gamma = float(request.get("gamma", 1.0))
        if gamma <= 0:
            return invalid("gamma must be positive")
        table = [round(255 * ((value / 255) ** (1 / gamma))) for value in range(256)]
        changed = changed.point(table * 3)
        stat = ImageStat.Stat(changed)
        means = stat.mean[:3]
        target = sum(means) / 3 or 1
        channels = changed.split()
        balanced = [channel.point(lambda value, scale=target / max(mean, 1): max(0, min(255, round(value * scale)))) for channel, mean in zip(channels, means)]
        changed = Image.merge("RGB", balanced)
        output, item = _save(changed, request, source, "quality-enhanced")
        return result(SkillStatus.SUCCESS, "Image quality enhancement completed", data={"output": output.name, "upscale": factor, "mode": "traditional"}, artifacts=[item], capabilities=capabilities)
    finally:
        image.close()


def execute(skill_name: str, request: dict[str, Any]) -> dict[str, Any]:
    operation = str(request.get("operation") or "").lower()
    batch_operations = {
        "image-toolkit": {"batch", "batch_convert", "batch_compress"},
        "photo-restoration": {"batch"},
        "image-background-tools": {"batch"},
        "image-quality-enhancer": {"batch"},
    }
    if operation in batch_operations.get(skill_name, set()):
        inputs = request.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            return invalid("batch operation requires a non-empty inputs list")
        item_operation = str(request.get("item_operation") or ({"batch_convert": "convert", "batch_compress": "compress"}.get(operation, "pipeline" if skill_name == "photo-restoration" else "remove_solid" if skill_name == "image-background-tools" else "enhance")))
        handler = {"image-toolkit": _image_toolkit, "photo-restoration": _photo_restoration, "image-background-tools": _background, "image-quality-enhancer": _quality}[skill_name]
        responses = []
        artifacts = []
        for input_path in inputs:
            child = dict(request); child["input"] = input_path; child["operation"] = item_operation; child.pop("inputs", None)
            response = handler(child); responses.append({"input": Path(str(input_path)).name, "status": response["status"], "message": response["message"]}); artifacts.extend(response.get("artifacts", []))
        failures = [item for item in responses if item["status"] not in {"SUCCESS", "PARTIAL_SUCCESS"}]
        status = SkillStatus.PARTIAL_SUCCESS if failures else SkillStatus.SUCCESS
        return result(status, "Batch image operation completed" if not failures else "Batch image operation completed with failures", data={"items": responses}, artifacts=artifacts, error_code="BATCH_ITEM_FAILED" if failures else None)
    if skill_name == "image-toolkit":
        return _image_toolkit(request)
    if skill_name == "photo-restoration":
        return _photo_restoration(request)
    if skill_name == "image-background-tools":
        return _background(request)
    if skill_name == "image-quality-enhancer":
        return _quality(request)
    return invalid(f"Unsupported image Skill: {skill_name}")
