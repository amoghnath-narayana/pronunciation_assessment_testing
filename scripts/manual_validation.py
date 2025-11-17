"""Manual validation script for TTS optimization.

This script provides a simple way to manually test the TTS system
and verify that optimization is working correctly.
"""

import logging
import time
from pathlib import Path

from config import AppConfig
from models.assessment_models import AssessmentResult, SpecificError
from services.gemini_service import GeminiAssessmentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run manual validation tests."""
    print("\n" + "="*80)
    print("TTS OPTIMIZATION MANUAL VALIDATION")
    print("="*80 + "\n")
    
    config = AppConfig()
    service = GeminiAssessmentService(config)
    
    # Check if optimization is enabled
    if service._composer:
        print("✓ TTS Optimization: ENABLED")
    else:
        print("✗ TTS Optimization: DISABLED (using legacy TTS)")
    
    print(f"  Assets directory: {config.tts_assets_dir}")
    print(f"  Cache directory: {config.tts_cache_dir}")
    print(f"  Manifest path: {config.tts_manifest_path}")
    
    # Check cache directory
    cache_dir = Path(config.tts_cache_dir)
    if cache_dir.exists():
        cache_files = list(cache_dir.rglob('*'))
        cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())
        print(f"  Cache size: {cache_size / (1024*1024):.2f}MB")
        print(f"  Cache entries: {len([f for f in cache_files if f.is_file()])}")
    else:
        print("  Cache: Not yet created")
    
    print("\n" + "-"*80)
    print("TEST 1: Perfect Reading (No Errors)")
    print("-"*80)
    
    perfect_assessment = AssessmentResult(specific_errors=[])
    
    start = time.perf_counter()
    audio = service.generate_tts_narration(perfect_assessment)
    latency = (time.perf_counter() - start) * 1000
    
    if audio:
        print(f"✓ Audio generated: {len(audio)} bytes")
        print(f"✓ Latency: {latency:.2f}ms")
        if latency < 50:
            print("✓ Performance: EXCELLENT (<50ms)")
        elif latency < 100:
            print("✓ Performance: GOOD (<100ms)")
        else:
            print("⚠ Performance: ACCEPTABLE but slower than target")
    else:
        print("✗ Failed to generate audio")
    
    print("\n" + "-"*80)
    print("TEST 2: Reading with Errors (First Time - Cache Miss)")
    print("-"*80)
    
    error_assessment = AssessmentResult(specific_errors=[
        SpecificError(
            word="vest",
            issue="You said 'best' instead of 'vest'",
            suggestion="Try emphasizing the 'v' sound at the beginning",
            severity="minor"
        ),
        SpecificError(
            word="test",
            issue="You said 'tess' instead of 'test'",
            suggestion="Make sure to pronounce the final 't' sound",
            severity="minor"
        )
    ])
    
    start = time.perf_counter()
    audio = service.generate_tts_narration(error_assessment)
    latency = (time.perf_counter() - start) * 1000
    
    if audio:
        print(f"✓ Audio generated: {len(audio)} bytes")
        print(f"✓ Latency: {latency:.2f}ms")
        if latency < 2000:
            print("✓ Performance: EXCELLENT (<2s)")
        elif latency < 5000:
            print("✓ Performance: GOOD (<5s)")
        else:
            print("⚠ Performance: Slower than expected (API calls required)")
    else:
        print("✗ Failed to generate audio")
    
    print("\n" + "-"*80)
    print("TEST 3: Same Errors Again (Cache Hit)")
    print("-"*80)
    
    start = time.perf_counter()
    audio = service.generate_tts_narration(error_assessment)
    latency = (time.perf_counter() - start) * 1000
    
    if audio:
        print(f"✓ Audio generated: {len(audio)} bytes")
        print(f"✓ Latency: {latency:.2f}ms")
        if latency < 100:
            print("✓ Performance: EXCELLENT (<100ms) - Cache working!")
        elif latency < 500:
            print("✓ Performance: GOOD (<500ms)")
        else:
            print("⚠ Performance: Cache may not be working optimally")
    else:
        print("✗ Failed to generate audio")
    
    print("\n" + "="*80)
    print("VALIDATION COMPLETE")
    print("="*80)
    print("\nKey Observations:")
    print("- Perfect readings should be <50ms (using pre-generated clips)")
    print("- First-time errors will be slower (requires TTS API calls)")
    print("- Repeated errors should be <100ms (using cache)")
    print("- All scenarios should successfully generate audio")
    print("\nIf optimization is disabled, all scenarios will use legacy TTS (~7s each)")
    print()


if __name__ == "__main__":
    main()
