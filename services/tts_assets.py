"""Service for loading and serving pre-generated TTS audio clips."""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import logfire
from pydantic import BaseModel, Field
from pydub import AudioSegment


class CategoryModel(BaseModel):
    """Pydantic model for a TTS asset category."""

    variants: List[str] = Field(min_length=1, description="List of audio file paths")


class ManifestModel(BaseModel):
    """Pydantic model for TTS manifest structure."""

    categories: Dict[str, CategoryModel] = Field(
        description="Dictionary of category names to category data"
    )


@dataclass
class TTSAssetLoader:
    """Loads and serves pre-generated TTS audio clips."""

    manifest_path: Path
    assets_dir: Path
    _manifest: Dict = field(default_factory=dict, init=False, repr=False)
    _audio_cache: Dict[str, List[AudioSegment]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self):
        """Initialize the asset loader by loading manifest and preloading assets.

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid or no assets were loaded
            Exception: If initialization fails for any other reason
        """
        self._manifest = self._load_manifest()
        self._preload_assets()

        # Validate that assets were actually loaded
        if not self._audio_cache:
            raise ValueError(
                "No audio assets were loaded successfully. Check manifest and asset files."
            )

        logfire.info(
            f"TTSAssetLoader initialized successfully with {len(self._audio_cache)} categories"
        )

    def _load_manifest(self) -> Dict:
        """Load and validate manifest.json using Pydantic.

        Returns:
            Dict: Parsed manifest data

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValidationError: If manifest structure is invalid
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {self.manifest_path}")

        with open(self.manifest_path, "r") as f:
            manifest_data = json.load(f)

        # Validate using Pydantic - raises ValidationError if invalid
        validated = ManifestModel.model_validate(manifest_data)

        logfire.info(
            f"Loaded manifest with {len(validated.categories)} categories"
        )
        return validated.model_dump()

    def _preload_assets(self):
        """Load all WAV files into memory as pydub AudioSegments.

        Loads all audio files referenced in the manifest into memory.
        Skips corrupted or missing files with error logging.
        """
        if not self._manifest or "categories" not in self._manifest:
            logfire.error("Cannot preload assets: manifest not loaded")
            return

        for category_name, category_data in self._manifest["categories"].items():
            loaded_variants = []

            for variant_path in category_data["variants"]:
                full_path = self.assets_dir / variant_path

                try:
                    if not full_path.exists():
                        logfire.error(f"Asset file not found: {full_path}")
                        continue

                    # Load audio file (supports WAV, MP3, and other formats pydub handles)
                    audio_segment = AudioSegment.from_file(str(full_path))
                    loaded_variants.append(audio_segment)
                    logfire.debug(f"Loaded asset: {variant_path}")

                except Exception as e:
                    logfire.error(f"Failed to load asset {full_path}: {e}")
                    continue

            if loaded_variants:
                self._audio_cache[category_name] = loaded_variants
                logfire.info(
                    f"Loaded {len(loaded_variants)} variants for category '{category_name}'"
                )
            else:
                logfire.warning(
                    f"No valid variants loaded for category '{category_name}'"
                )

    def pick(self, category: str) -> AudioSegment:
        """Return random variant for category.

        Args:
            category: Name of the category to pick from

        Returns:
            AudioSegment: Randomly selected audio variant

        Raises:
            ValueError: If category doesn't exist or has no loaded variants
        """
        if category not in self._audio_cache:
            raise ValueError(
                f"Category '{category}' not found or has no loaded variants"
            )

        variants = self._audio_cache[category]
        if not variants:
            raise ValueError(f"Category '{category}' has no available variants")

        selected = random.choice(variants)
        logfire.debug(
            f"Selected random variant from category '{category}' ({len(variants)} available)"
        )
        return selected
