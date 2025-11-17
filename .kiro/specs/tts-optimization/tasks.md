# Implementation Plan

- [x] 1. Set up project infrastructure and dependencies

  - Add pydub==0.25.1 and diskcache==5.6.3 to requirements.txt
  - Create assets/tts/ directory structure with subdirectories for each category
  - Extend AppConfig in config.py with new fields: tts_assets_dir, tts_manifest_path, tts_cache_dir, tts_cache_size_mb, tts_enable_optimization
  - Update .env.template with new configuration variables and default values
  - _Requirements: 3.6, 5.1, 5.2_

- [x] 2. Implement TTSAssetLoader service

  - Create services/tts_assets.py with TTSAssetLoader dataclass
  - Implement \_load_manifest() method to parse and validate manifest.json structure
  - Implement \_preload_assets() method to load all WAV files into memory as pydub AudioSegments
  - Implement pick(category) method to return random variant using random.choice
  - Implement is_available() method to check if assets loaded successfully
  - Add error handling for missing/corrupted files with logging
  - _Requirements: 2.1, 2.2, 5.3, 5.4_

- [x] 3. Implement TTSCacheService with diskcache

  - Create services/tts_cache.py with TTSCacheService dataclass
  - Initialize diskcache.Cache in **post_init** with cache_dir and size_limit parameters
  - Implement \_generate_cache_key() method using SHA256 hash of text + voice_name
  - Implement get_or_generate() method with cache lookup and fallback to TTS generation
  - Implement \_generate_tts() method by extracting current Gemini TTS API call logic
  - Add logging for cache hits/misses
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 4. Implement TTSNarrationComposer for audio assembly

  - Create services/tts_composer.py with TTSNarrationComposer dataclass
  - Implement compose() method to handle perfect reading case (single intro clip)
  - Implement compose() method to handle error case (intro + dynamic errors + outro)
  - Implement \_normalize_loudness() method using pydub's normalize() or match_target_amplitude(-20)
  - Implement \_export_wav() method to convert AudioSegment to WAV bytes
  - Add error handling with fallback signaling for missing assets
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.6_

- [x] 5. Modify GeminiAssessmentService to use composer

  - Add **post_init** method to initialize TTSNarrationComposer when tts_enable_optimization is True
  - Implement \_initialize_composer() method to instantiate TTSAssetLoader, TTSCacheService, and TTSNarrationComposer
  - Refactor existing generate_tts_narration() logic into new \_generate_tts_legacy() method
  - Update generate_tts_narration() to delegate to composer with try/except fallback to legacy
  - Add logging for optimization enabled/disabled and fallback scenarios
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Create TTS asset generation tooling

  - Create scripts/generate_tts_assets.py script to generate static clip variations
  - Implement function to call Gemini TTS API with varied prompts for each category
  - Implement loudness normalization across all generated clips to -20 dBFS
  - Generate 4 variants each for: perfect_intro, needs_work_intro, closing_cheer
  - Save generated clips to assets/tts/<category>/variant_N.wav
  - Create assets/tts/manifest.json with category definitions and variant file paths
  - _Requirements: 2.1, 2.2, 5.1, 5.2, 5.3_

- [x] 7. Validate integration and performance
  - Run assessment with no errors and verify perfect_intro clip plays within 50ms
  - Run assessment with new errors and verify cache miss generates TTS within 2 seconds
  - Run assessment with repeated errors and verify cache hit returns audio within 100ms
  - Test fallback by removing manifest.json and verify legacy TTS still works
  - Verify cache directory stays under 500MB limit after 100+ assessments
  - Check logs for cache hit rate and confirm >70% after warm-up period
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 6.7_
