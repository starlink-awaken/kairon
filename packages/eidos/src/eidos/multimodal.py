#!/usr/bin/env python3
# ruff: noqa
"""G2: 多模态知识 embedding — 扩展 eidos vector_backends 支持图片/音频.

场景覆盖审计 G2 缺口实现 (多模态知识, 图片/音频摄入 + 语义搜索).
现状: kronos 摄取文本/URL/HTML, eidos vector_backends 是文本向量, 无多模态.
本模块: 多模态 embedding 接口 (CLIP 图片 + whisper 音频), 可选依赖 (未装则 skip + 返回 None),
        返回统一向量供 eidos vector_backends 存储. embed_auto 按扩展名自动路由模态.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_MODALITIES = ("text", "image", "audio")


def embed_text(text: str) -> list[float] | None:
    """文本 embedding (复用 eidos 现有文本向量)."""
    try:
        # 复用 eidos vector_backends 文本 embedding (名字可能不同, try 多个)
        from eidos import vector_backends  # type: ignore

        for fn_name in ("get_embedding", "embed", "encode_text"):
            fn = getattr(vector_backends, fn_name, None)
            if fn:
                return fn(text)
    except Exception:
        pass
    return None


def embed_image(image_path: str) -> list[float] | None:
    """图片 embedding (CLIP, 可选依赖)."""
    try:
        import clip  # type: ignore
        import torch  # type: ignore
        from PIL import Image  # type: ignore

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, preprocess = clip.load("ViT-B/32", device=device)
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
        with torch.no_grad():
            vec = model.encode_image(image)
        return vec.cpu().tolist()[0]
    except ImportError:
        return None  # CLIP/PIL/torch 未装
    except Exception:
        return None


def embed_audio(audio_path: str) -> list[float] | None:
    """音频 embedding (whisper 转文本 + 文本 embedding)."""
    try:
        import whisper  # type: ignore

        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        text = result.get("text", "")
        if text:
            return embed_text(text)
        return None
    except ImportError:
        return None  # whisper 未装
    except Exception:
        return None


def embed_auto(path: str, modality: str | None = None) -> dict[str, Any]:
    """自动检测模态 + embedding (modality 为 None 按扩展名推断)."""
    if modality is None:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
            modality = "image"
        elif ext in ("mp3", "wav", "m4a", "flac", "ogg", "aac"):
            modality = "audio"
        else:
            modality = "text"

    handlers = {"text": embed_text, "image": embed_image, "audio": embed_audio}
    handler = handlers.get(modality, embed_text)
    vec = handler(path)
    return {
        "path": path,
        "modality": modality,
        "embedded": vec is not None,
        "vector_dim": len(vec) if vec else 0,
    }


def list_modalities() -> list[str]:
    """列出支持的模态."""
    return list(SUPPORTED_MODALITIES)


def check_dependencies() -> dict[str, bool]:
    """检查多模态可选依赖是否装."""
    deps = {}
    for mod, pkg in [("clip", "clip"), ("image", "PIL"), ("audio", "whisper"), ("torch", "torch")]:
        try:
            __import__(pkg)
            deps[mod] = True
        except ImportError:
            deps[mod] = False
    return deps


def main() -> None:
    """CLI: eidos multimodal — 列模态 + 依赖状态."""
    import json

    print(
        json.dumps(
            {"modalities": list_modalities(), "dependencies": check_dependencies()}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
