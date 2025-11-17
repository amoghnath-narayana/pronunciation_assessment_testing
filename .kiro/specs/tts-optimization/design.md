# TTS Optimization Design Document

## Overview

This design replaces the current monolithic TTS generation approach with a hybrid system that combines pre-generated static audio clips with cached dynamic TTS segments. The architecture maintains the existing `GeminiAssessmentService.generate_tts_narration()` signature while internally delegating to a new `TTSNarrationComposer` that assembles audio from multiple sources.

**Key Design Principles:**

- Zero breaking changes to existing API contracts
- Library-first approach (pydub, diskcache) over custom implementations
- Fail-safe fallbacks to current behavior when assets/cache unavailable
- Stateless composition for thread safety in Streamlit

## Architecture

### High-Level Flow

```
AssessmentResult → build_tts_narration_prompt() → Narration Text
                                                         ↓
                                    TTSNarrationComposer.compose()
                                                         ↓
                        ┌────────────────────────────────┴────────────────────────────┐
                        ↓                                                              ↓
              Static Clips (pre-generated)                              Dynamic Clips (on-demand)
                        ↓                                                              ↓
              TTSAssetLoader.pick()                                    TTSCacheService.get_or_generate()
                        ↓                                                              ↓
              Random WAV from manifest                                 diskcache → Gemini TTS API
                        ↓                                                              ↓
                        └────────────────────────────────┬────────────────────────────┘
                                                         ↓
                                    pydub.AudioSegment concatenation
                                                         ↓
                                              Final WAV bytes → Streamlit
```

### Component Responsibilities

1. **TTSNarrationComposer** (services/tts_composer.py)

   - Orchestrates the composition of final audio
   - Parses narration text into segments (intro, errors, outro)
   - Delegates to asset loader and cache service
   - Handles fallback to legacy single-call TTS

2. **TTSAssetLoader** (services/tts_assets.py)

   - Loads manifest.json on initialization
   - Validates asset files exist
   - Provides `pick(category: str) -> bytes` for random selection
   - Caches loaded AudioSegments in memory

3. **TTSCacheService** (services/tts_cache.py)

   - Wraps diskcache.Cache with TTS-specific logic
   - Generates cache keys from (text, voice_name)
   - Calls Gemini TTS API on cache miss
   - Returns WAV bytes

4. **GeminiAssessmentService** (services/gemini_service.py - modified)
   - `generate_tts_narration()` delegates to TTSNarrationComposer
   - Maintains existing method signature
   - Handles exceptions and fallback

## Components and Interfaces

### 1. Configuration Extensions

**File:** `config.py`

```python
class AppConfig(BaseSettings):
    # ... existing fields ...

    # TTS Optimization
    tts_assets_dir: str = "assets/tts"
    tts_manifest_path: str = "assets/tts/manifest.json"
    tts_cache_dir: str = "assets/tts/cache"
    tts_cache_size_mb: int = 500
    tts_enable_optimization: bool = True  # Feature flag for rollback
```

### 2. Asset Manifest Schema

**File:** `assets/tts/manifest.json`

```json
{
  "version": "1.0",
  "voice_name": "Aoede",
  "categories": {
    "perfect_intro": {
      "intent": "Celebration for error-free reading",
      "variants": [
        "perfect_intro/variant_1.wav",
        "perfect_intro/variant_2.wav",
        "perfect_intro/variant_3.wav",
        "perfect_intro/variant_4.wav"
      ]
    },
    "needs_work_intro": {
      "intent": "Encouraging lead-in before corrections",
      "variants": [
        "needs_work_intro/variant_1.wav",
        "needs_work_intro/variant_2.wav",
        "needs_work_intro/variant_3.wav",
        "needs_work_intro/variant_4.wav"
      ]
    },
    "closing_cheer": {
      "intent": "Positive ending after corrections",
      "variants": [
        "closing_cheer/variant_1.wav",
        "closing_cheer/variant_2.wav",
        "closing_cheer/variant_3.wav",
        "closing_cheer/variant_4.wav"
      ]
    }
  }
}
```

### 3. TTSAssetLoader Interface

**File:** `services/tts_assets.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import json
import random
from pydub import AudioSegment

@dataclass
class TTSAssetLoader:
    """Loads and serves pre-generated TTS audio clips."""

    manifest_path: Path
    assets_dir: Path

    def __post_init__(self):
        self._manifest: Dict = self._load_manifest()
        self._audio_cache: Dict[str, List[AudioSegment]] = {}
        self._preload_assets()

    def _load_manifest(self) -> Dict:
        """Load and validate manifest.json."""
        # Returns parsed JSON with validation
        pass

    def _preload_assets(self):
        """Load all WAV files into memory as AudioSegments."""
        # Iterates categories, loads variants
        pass

    def pick(self, category: str) -> AudioSegment:
        """Return random variant for category."""
        # random.choice from cached AudioSegments
        pass

    def is_available(self) -> bool:
        """Check if assets loaded successfully."""
        pass
```

### 4. TTSCacheService Interface

**File:** `services/tts_cache.py`

```python
from dataclasses import dataclass
from pathlib import Path
import hashlib
import diskcache
from google import genai
from google.genai import types

@dataclass
class TTSCacheService:
    """Manages cached TTS audio with diskcache."""

    cache_dir: Path
    cache_size_mb: int
    gemini_client: genai.Client
    tts_config: Dict  # model_name, voice_name, voice_style_prompt

    def __post_init__(self):
        self._cache = diskcache.Cache(
            str(self.cache_dir),
            size_limit=self.cache_size_mb * 1024 * 1024
        )

    def _generate_cache_key(self, text: str) -> str:
        """Create hash key from text + voice config."""
        # SHA256 of text + voice_name
        pass

    def get_or_generate(self, text: str) -> bytes:
        """Return cached WAV or generate via Gemini TTS."""
        key = self._generate_cache_key(text)

        if key in self._cache:
            return self._cache[key]

        # Call Gemini TTS API (same as current generate_tts_narration)
        wav_bytes = self._generate_tts(text)
        self._cache[key] = wav_bytes
        return wav_bytes

    def _generate_tts(self, text: str) -> bytes:
        """Call Gemini TTS API and convert to WAV."""
        # Identical to current GeminiAssessmentService.generate_tts_narration
        pass
```

### 5. TTSNarrationComposer Interface

**File:** `services/tts_composer.py`

```python
from dataclasses import dataclass
from pydub import AudioSegment
from models.assessment_models import AssessmentResult
from prompts import build_tts_narration_prompt

@dataclass
class TTSNarrationComposer:
    """Composes final TTS audio from static and dynamic segments."""

    asset_loader: TTSAssetLoader
    cache_service: TTSCacheService

    def compose(self, assessment_result: AssessmentResult) -> bytes:
        """Build final audio from assessment result."""

        # Handle perfect reading case
        if not assessment_result.specific_errors:
            intro = self.asset_loader.pick("perfect_intro")
            return self._export_wav(intro)

        # Build segments for errors
        segments = []

        # Intro
        intro = self.asset_loader.pick("needs_work_intro")
        segments.append(intro)

        # Dynamic error corrections
        for error in assessment_result.specific_errors:
            error_text = f"For the word '{error.word}': {error.issue} {error.suggestion}"
            error_audio_bytes = self.cache_service.get_or_generate(error_text)
            error_segment = AudioSegment.from_wav(io.BytesIO(error_audio_bytes))
            segments.append(error_segment)

        # Outro
        outro = self.asset_loader.pick("closing_cheer")
        segments.append(outro)

        # Concatenate and normalize
        final_audio = sum(segments)
        normalized = self._normalize_loudness(final_audio)

        return self._export_wav(normalized)

    def _normalize_loudness(self, audio: AudioSegment) -> AudioSegment:
        """Apply loudness normalization to prevent volume jumps."""
        # pydub normalize() or match_target_amplitude()
        pass

    def _export_wav(self, audio: AudioSegment) -> bytes:
        """Export AudioSegment to WAV bytes."""
        # audio.export(format="wav")
        pass
```

### 6. Modified GeminiAssessmentService

**File:** `services/gemini_service.py`

```python
@dataclass
class GeminiAssessmentService:
    config: AppConfig

    def __post_init__(self):
        if self.config.tts_enable_optimization:
            try:
                self._composer = self._initialize_composer()
            except Exception as e:
                st.warning(f"TTS optimization unavailable: {e}. Using fallback.")
                self._composer = None
        else:
            self._composer = None

    def _initialize_composer(self) -> TTSNarrationComposer:
        """Initialize TTS composer with dependencies."""
        asset_loader = TTSAssetLoader(
            manifest_path=Path(self.config.tts_manifest_path),
            assets_dir=Path(self.config.tts_assets_dir)
        )

        cache_service = TTSCacheService(
            cache_dir=Path(self.config.tts_cache_dir),
            cache_size_mb=self.config.tts_cache_size_mb,
            gemini_client=self.client,
            tts_config={
                "model_name": self.config.tts_model_name,
                "voice_name": self.config.tts_voice_name,
                "voice_style_prompt": self.config.tts_voice_style_prompt
            }
        )

        return TTSNarrationComposer(
            asset_loader=asset_loader,
            cache_service=cache_service
        )

    def generate_tts_narration(self, assessment_result: AssessmentResult) -> bytes:
        """Generate TTS audio from assessment result."""

        # Use optimized path if available
        if self._composer:
            try:
                return self._composer.compose(assessment_result)
            except Exception as e:
                st.warning(f"TTS composition failed: {e}. Using fallback.")

        # Fallback to current implementation
        return self._generate_tts_legacy(assessment_result)

    def _generate_tts_legacy(self, assessment_result: AssessmentResult) -> bytes:
        """Original single-call TTS generation (current implementation)."""
        # Move existing generate_tts_narration logic here
        pass
```

## Data Models

No new Pydantic models required. Existing `AssessmentResult` and `SpecificError` models remain unchanged.

## Error Handling

### Failure Scenarios and Responses

1. **Missing manifest.json**

   - Log warning: "TTS assets not found, using legacy TTS"
   - Fall back to `_generate_tts_legacy()`
   - Application continues normally

2. **Corrupted asset files**

   - Skip corrupted variants during `_preload_assets()`
   - Log error for each failed file
   - Continue with available variants
   - If category has zero valid variants, fall back to legacy

3. **diskcache initialization failure**

   - Log warning: "TTS cache unavailable"
   - Proceed without caching (direct TTS generation)
   - Performance degrades but functionality preserved

4. **Gemini TTS API failure**

   - Retry once with exponential backoff
   - If still fails, return None and show error in UI
   - Same behavior as current implementation

5. **pydub concatenation failure**
   - Log error with segment details
   - Fall back to legacy single-call TTS
   - Ensures user always gets audio feedback

### Logging Strategy

```python
import logging

logger = logging.getLogger(__name__)

# Asset loading
logger.info(f"Loaded {len(variants)} variants for category '{category}'")
logger.error(f"Failed to load asset {path}: {error}")

# Cache operations
logger.debug(f"Cache hit for key {key[:8]}...")
logger.debug(f"Cache miss, generating TTS for text: {text[:50]}...")

# Composition
logger.info(f"Composed audio: {len(segments)} segments, {duration}s total")
logger.warning(f"Falling back to legacy TTS: {reason}")
```

## Testing Strategy

### Unit Tests

**File:** `tests/test_tts_assets.py`

- Test manifest loading with valid/invalid JSON
- Test variant selection randomness
- Test handling of missing files

**File:** `tests/test_tts_cache.py`

- Test cache key generation consistency
- Test cache hit/miss behavior
- Test size limit enforcement

**File:** `tests/test_tts_composer.py`

- Test perfect reading composition (single intro clip)
- Test error composition (intro + errors + outro)
- Test loudness normalization
- Test fallback on missing assets

### Integration Tests

**File:** `tests/test_gemini_service_integration.py`

- Test `generate_tts_narration()` with optimization enabled
- Test fallback when assets unavailable
- Test end-to-end with real AssessmentResult objects
- Verify output WAV format matches current implementation

### Manual Testing Checklist

1. Generate 4-5 static clip variations using Gemini TTS with `tts_voice_name` from config
2. Place clips in `assets/tts/` structure
3. Run assessment with common errors, verify cache hits in logs
4. Delete manifest.json, verify fallback to legacy TTS
5. Monitor cache directory size stays under 500MB
6. Test with 10 different children making same error, verify audio reuse

## Performance Considerations

### Memory Usage

- **Static clips:** ~4 categories × 4 variants × 50KB = ~800KB in memory
- **diskcache:** Handles memory automatically, 500MB disk limit
- **pydub operations:** Temporary AudioSegment objects, garbage collected after export

### Latency Targets

| Scenario                   | Current | Target | Improvement |
| -------------------------- | ------- | ------ | ----------- |
| Perfect reading            | ~7s     | <50ms  | 140x faster |
| New error (cache miss)     | ~7s     | ~1.5s  | 4.7x faster |
| Repeated error (cache hit) | ~7s     | <100ms | 70x faster  |

### Token Consumption

- **Current:** ~60 tokens per narration × 1000 assessments = 60,000 tokens/day
- **Optimized:** ~15 tokens per dynamic clip × 2 errors × 30% cache miss rate × 1000 = 9,000 tokens/day
- **Savings:** 85% reduction (better than 75% target)

## Dependencies

### New Libraries

Add to `requirements.txt`:

```
pydub==0.25.1
diskcache==5.6.3
```

### System Dependencies

- **ffmpeg** (required by pydub for audio format conversion)
  - Installation: `brew install ffmpeg` (macOS)
  - Verify: `ffmpeg -version`

## Migration Plan

### Phase 1: Infrastructure Setup

1. Add new config fields to `.env.template`
2. Create `assets/tts/` directory structure
3. Install pydub and diskcache

### Phase 2: Generate Static Assets

1. Use Gemini TTS to generate 4 variants per category
2. Normalize loudness across all clips
3. Create manifest.json

### Phase 3: Implementation

1. Implement TTSAssetLoader with tests
2. Implement TTSCacheService with tests
3. Implement TTSNarrationComposer with tests
4. Modify GeminiAssessmentService with feature flag

### Phase 4: Validation

1. Deploy with `tts_enable_optimization=False` (no changes)
2. Enable optimization for 10% of traffic
3. Monitor logs for errors and cache hit rate
4. Gradually increase to 100%

### Rollback Strategy

If issues arise:

1. Set `tts_enable_optimization=False` in config
2. Application immediately reverts to legacy TTS
3. No code deployment needed
4. Investigate issues offline

## Open Questions

1. **Asset generation workflow:** Should we provide a script to auto-generate variants, or document manual process?

   - Recommendation: Create `scripts/generate_tts_assets.py` that calls Gemini TTS with varied prompts

2. **Cache eviction policy:** Should we use LRU (diskcache default) or custom policy?

   - Recommendation: Use default LRU, monitor in production

3. **Loudness normalization target:** What dBFS level should we normalize to?

   - Recommendation: -20 dBFS (standard for speech, not too loud/quiet)

4. **Monitoring:** Should we track cache hit rate in production?
   - Recommendation: Yes, log every 100 assessments for visibility
