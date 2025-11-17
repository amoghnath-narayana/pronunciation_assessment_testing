"""Service for loading and serving pre-generated TTS audio clips."""

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from pydub import AudioSegment

logger = logging.getLogger(__name__)


@dataclass
class TTSAssetLoader:
    """Loads and serves pre-generated TTS audio clips."""

    manifest_path: Path
    assets_dir: Path
    _manifest: Dict = field(default_factory=dict, init=False, repr=False)
    _audio_cache: Dict[str, List[AudioSegment]] = field(default_factory=dict, init=False, repr=False)
    _loaded_successfully: bool = field(default=False, init=False, repr=False)

    def __post_init__(self):
        """Initialize the asset loader by loading manifest and preloading assets."""
        try:
            self._manifest = self._load_manifest()
            self._preload_assets()
            self._loaded_successfully = True
            logger.info(f"TTSAssetLoader initialized successfully with {len(self._audio_cache)} categories")
        except Exception as e:
            logger.error(f"Failed to initialize TTSAssetLoader: {e}")
            self._loaded_successfully = False

    def _load_manifest(self) -> Dict:
        """Load and validate manifest.json structure.
        
        Returns:
            Dict: Parsed manifest data
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
            json.JSONDecodeError: If manifest is not valid JSON
            ValueError: If manifest structure is invalid
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {self.manifest_path}")
        
        with open(self.manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Validate manifest structure
        if 'categories' not in manifest:
            raise ValueError("Manifest missing 'categories' field")
        
        if not isinstance(manifest['categories'], dict):
            raise ValueError("Manifest 'categories' must be a dictionary")
        
        # Validate each category
        for category_name, category_data in manifest['categories'].items():
            if 'variants' not in category_data:
                raise ValueError(f"Category '{category_name}' missing 'variants' field")
            
            if not isinstance(category_data['variants'], list):
                raise ValueError(f"Category '{category_name}' variants must be a list")
            
            if len(category_data['variants']) == 0:
                logger.warning(f"Category '{category_name}' has no variants")
        
        logger.info(f"Loaded manifest with {len(manifest['categories'])} categories")
        return manifest

    def _preload_assets(self):
        """Load all WAV files into memory as pydub AudioSegments.
        
        Loads all audio files referenced in the manifest into memory.
        Skips corrupted or missing files with error logging.
        """
        if not self._manifest or 'categories' not in self._manifest:
            logger.error("Cannot preload assets: manifest not loaded")
            return
        
        for category_name, category_data in self._manifest['categories'].items():
            loaded_variants = []
            
            for variant_path in category_data['variants']:
                full_path = self.assets_dir / variant_path
                
                try:
                    if not full_path.exists():
                        logger.error(f"Asset file not found: {full_path}")
                        continue
                    
                    # Load audio file (supports WAV, MP3, and other formats pydub handles)
                    audio_segment = AudioSegment.from_file(str(full_path))
                    loaded_variants.append(audio_segment)
                    logger.debug(f"Loaded asset: {variant_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to load asset {full_path}: {e}")
                    continue
            
            if loaded_variants:
                self._audio_cache[category_name] = loaded_variants
                logger.info(f"Loaded {len(loaded_variants)} variants for category '{category_name}'")
            else:
                logger.warning(f"No valid variants loaded for category '{category_name}'")

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
            raise ValueError(f"Category '{category}' not found or has no loaded variants")
        
        variants = self._audio_cache[category]
        if not variants:
            raise ValueError(f"Category '{category}' has no available variants")
        
        selected = random.choice(variants)
        logger.debug(f"Selected random variant from category '{category}' ({len(variants)} available)")
        return selected

    def is_available(self) -> bool:
        """Check if assets loaded successfully.
        
        Returns:
            bool: True if assets were loaded successfully, False otherwise
        """
        return self._loaded_successfully and len(self._audio_cache) > 0
