# TTS Optimization Validation Scripts

This directory contains validation scripts for the TTS optimization feature.

## Available Scripts

### 1. `validate_tts_performance.py`

Comprehensive automated test suite that validates all performance requirements.

**Usage:**

```bash
python -m scripts.validate_tts_performance
```

**Tests:**

- ✓ Perfect reading latency (<50ms)
- ⚠ Cache miss latency (<2s) - Currently ~15s for 2 errors
- ✓ Cache hit latency (<100ms)
- ✓ Fallback behavior (missing manifest)
- Cache size limit (optional, requires extended runtime)
- Cache hit rate (optional, requires extended runtime)

**Note**: The cache miss test will take ~15 seconds per run as it makes real API calls.

---

### 2. `manual_validation.py`

Quick manual validation for verifying the system is working correctly.

**Usage:**

```bash
python -m scripts.manual_validation
```

**Output:**

- System status (optimization enabled/disabled)
- Cache statistics (size, entries)
- Three test scenarios with timing
- Performance assessment

**Recommended for:**

- Quick health checks
- Verifying deployment
- Demonstrating the feature

---

### 3. `generate_tts_assets.py`

Script for generating pre-recorded TTS audio clips.

**Usage:**

```bash
python -m scripts.generate_tts_assets
```

**Purpose:**

- Generate static audio clips for common phrases
- Create manifest.json
- Normalize audio levels

---

## Validation Results

See `docs/TTS_VALIDATION_RESULTS.md` for detailed validation results and analysis.

## Quick Start

To validate the TTS optimization is working:

1. **Run manual validation:**

   ```bash
   python -m scripts.manual_validation
   ```

2. **Check output:**

   - Perfect reading should be <50ms
   - Cached errors should be <100ms
   - All tests should generate audio

3. **Verify cache:**
   ```bash
   ls -lh assets/tts/cache
   ```

## Troubleshooting

### "TTS optimization unavailable"

**Cause**: Missing manifest.json or corrupted assets

**Solution**:

1. Check `assets/tts/manifest.json` exists
2. Verify all variant files referenced in manifest exist
3. Re-run `python -m scripts.generate_tts_assets` if needed

### "Cache not working"

**Cause**: Cache directory permissions or diskcache issues

**Solution**:

1. Check `assets/tts/cache` directory exists and is writable
2. Clear cache: `rm -rf assets/tts/cache/*`
3. Restart application

### "Slow performance"

**Cause**: Cache miss (first-time errors) or API latency

**Expected**:

- First-time errors: ~7s per error (API call required)
- Repeated errors: <100ms (cache hit)
- Perfect readings: <50ms (pre-generated clip)

## Performance Expectations

| Scenario             | Expected Latency | Notes                   |
| -------------------- | ---------------- | ----------------------- |
| Perfect reading      | <50ms            | Uses pre-generated clip |
| First-time error     | ~7s per error    | Requires API call       |
| Cached error         | <100ms           | Retrieved from cache    |
| Fallback (no assets) | ~7s              | Uses legacy TTS         |

## Monitoring

To monitor cache performance in production:

1. **Check cache size:**

   ```bash
   du -sh assets/tts/cache
   ```

2. **Count cache entries:**

   ```bash
   find assets/tts/cache -type f | wc -l
   ```

3. **View logs:**
   Look for log messages containing:
   - "Cache hit" / "Cache miss"
   - "Composing perfect reading"
   - "Composing error narration"

## Feature Flag

To disable optimization and use legacy TTS:

```bash
# In .env file
tts_enable_optimization=False
```

This will cause all TTS generation to use the original single-call approach (~7s per narration).
