# Requirements Document

## Introduction

This feature optimizes the Text-to-Speech (TTS) narration system by replacing the current monolithic TTS generation with a hybrid approach: pre-generated audio clips for common phrases and cached dynamic segments for unique word corrections. The goal is to reduce TTS latency from ~7 seconds to <2 seconds while maintaining variety and reducing API token consumption by 75%.

## Glossary

- **TTS System**: The Text-to-Speech narration generation component that provides audio feedback to users
- **Static Clip**: Pre-recorded audio segment for common phrases (intros, outros, connectors) stored as WAV/MP3 files
- **Dynamic Clip**: On-demand synthesized TTS audio for unique narration text (e.g., "For the word 'vest', say 'vest' not 'best'") generated via Gemini TTS API
- **Narration Composer**: Service component that assembles final audio by concatenating static and dynamic clips using pydub library
- **Audio Concatenation Library**: pydub AudioSegment used to join, normalize, and export audio clips
- **Assessment Result**: Structured data containing pronunciation errors and severity levels from GeminiAssessmentService (NOT cached - each assessment is unique)
- **Cache Layer**: Storage for previously generated TTS audio clips keyed by narration text content, using diskcache library for automatic persistence
- **Gemini TTS API**: Google's Gemini 2.5 text-to-speech model accessed via responseModalities=["AUDIO"]

## Requirements

### Requirement 1

**User Story:** As a child user, I want to receive audio feedback immediately after my pronunciation attempt, so that I stay engaged and don't lose focus waiting.

#### Acceptance Criteria

1. WHEN the Assessment Result contains no errors, THE TTS System SHALL play a pre-generated success intro within 50 milliseconds
2. WHEN the Assessment Result contains previously encountered errors, THE TTS System SHALL retrieve cached Dynamic Clips and play complete narration within 100 milliseconds
3. WHEN the Assessment Result contains new errors, THE TTS System SHALL generate Dynamic Clips and play complete narration within 2 seconds
4. THE TTS System SHALL maintain perceived latency below 2 seconds for 95% of assessments

### Requirement 2

**User Story:** As a child user, I want to hear varied encouragement phrases across multiple practice sessions, so that the feedback feels fresh and engaging rather than repetitive.

#### Acceptance Criteria

1. THE TTS System SHALL maintain at least 4 distinct Static Clip variations for each narration category
2. WHEN assembling narration, THE Narration Composer SHALL randomly select one variation from the available Static Clips for each category
3. THE TTS System SHALL support the following categories: perfect_intro, needs_work_intro, severity_connector, praise_bridge, closing_cheer
4. WHERE a category has 5 variations, THE Narration Composer SHALL select each with equal probability

### Requirement 3

**User Story:** As a developer, I want the TTS optimization to integrate seamlessly with existing code, so that I can deploy the feature without breaking current functionality.

#### Acceptance Criteria

1. THE TTS System SHALL preserve the existing GeminiAssessmentService.generate_tts_narration method signature
2. WHEN Static Clips are missing or corrupted, THE TTS System SHALL fall back to the current single-call narration approach
3. WHEN Dynamic Clip generation fails, THE TTS System SHALL log a warning and attempt fallback narration
4. THE TTS System SHALL return audio bytes in the same WAV format currently consumed by Streamlit st.audio
5. THE TTS System SHALL require no changes to app.py or ui/components.py
6. THE Narration Composer SHALL use pydub AudioSegment for concatenating audio clips and normalizing loudness

### Requirement 4

**User Story:** As a system operator, I want to reduce API token consumption and costs, so that the application scales economically as usage grows.

#### Acceptance Criteria

1. THE TTS System SHALL reduce per-assessment token usage by at least 75% compared to the baseline single-call approach
2. THE Cache Layer SHALL achieve at least 70% hit rate after the first 100 assessments with common practice sentences
3. WHEN processing 1000 assessments with average 2 errors each, THE TTS System SHALL consume no more than 15,000 tokens for Dynamic Clip generation

### Requirement 5

**User Story:** As a content manager, I want to easily add or update pre-generated audio variations, so that I can improve narration quality without code changes.

#### Acceptance Criteria

1. THE TTS System SHALL load Static Clips from a manifest file at assets/tts/manifest.json
2. THE manifest file SHALL define each category with fields: category_name, intent_description, and variant_file_paths
3. WHEN the manifest is updated, THE TTS System SHALL reload Static Clips on the next assessment without requiring application restart
4. THE TTS System SHALL validate that all variant files referenced in the manifest exist and are readable WAV or MP3 files
5. WHERE a variant file is missing, THE TTS System SHALL log an error and exclude that variant from random selection

### Requirement 6

**User Story:** As a developer, I want TTS narration audio to be cached by text content using a proven library, so that identical feedback messages reuse the same audio without affecting assessment accuracy.

#### Acceptance Criteria

1. THE TTS System SHALL perform a fresh pronunciation assessment for every audio recording without any caching
2. THE Cache Layer SHALL only cache the TTS audio output generated from the narration text, never the Assessment Result itself
3. THE Cache Layer SHALL use diskcache.Cache library keyed by the narration text content and voice configuration
4. WHEN two different children produce the same error pattern, THE TTS System SHALL assess each recording independently but MAY reuse the cached TTS audio for identical narration text
5. THE Cache Layer SHALL initialize diskcache.Cache with the directory path specified in AppConfig.tts_cache_dir
6. THE Cache Layer SHALL configure diskcache with size_limit parameter to cap total cache size at 500MB
7. THE TTS System SHALL ensure narration text contains no child-specific identifiers (names, timestamps, recording IDs) that would prevent safe caching

### Requirement 7

**User Story:** As a developer, I want the TTS system to comply with Gemini API documentation, so that the implementation remains supported and maintainable.

#### Acceptance Criteria

1. THE TTS System SHALL use Gemini 2.5 model with responseModalities=["AUDIO"] for all Dynamic Clip generation
2. THE TTS System SHALL configure speech_config.voice_config.prebuilt_voice_config.voice_name using a supported voice from the Gemini API
3. THE TTS System SHALL accept text prompts between 1 and 500 characters for Dynamic Clip generation
4. THE TTS System SHALL convert inline PCM audio data to WAV format using the same approach documented in docs/speech-generation.md.txt
5. THE TTS System SHALL use natural language prompts to control tone and style as recommended in Gemini documentation
