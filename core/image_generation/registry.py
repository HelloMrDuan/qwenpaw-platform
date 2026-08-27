"""In-process registry for replaceable image-generation providers."""

from __future__ import annotations

from .provider import ImageGenerationProvider


class ImageGenerationProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ImageGenerationProvider] = {}

    def register(self, provider: ImageGenerationProvider) -> None:
        if not isinstance(provider, ImageGenerationProvider):
            raise TypeError("provider must implement ImageGenerationProvider")
        name = provider.name.strip()
        if not name:
            raise ValueError("provider name must be non-empty")
        if name in self._providers:
            raise ValueError(f"image-generation provider already registered: {name}")
        self._providers[name] = provider

    def get(self, name: str) -> ImageGenerationProvider | None:
        return self._providers.get(name)

    def list(self) -> tuple[ImageGenerationProvider, ...]:
        return tuple(self._providers[name] for name in sorted(self._providers))
