"""Validation script for TTS optimization integration and performance.

This script validates:
1. Perfect reading scenario (no errors) - <50ms latency
2. New errors scenario (cache miss) - <2s latency
3. Repeated errors scenario (cache hit) - <100ms latency
4. Fallback behavior when manifest.json is missing
5. Cache size stays under 500MB limit
6. Cache hit rate >70% after warm-up period
"""

import io
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import List, Tuple

from config import AppConfig
from models.assessment_models import AssessmentResult, SpecificError
from services.gemini_service import GeminiAssessmentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceValidator:
    """Validates TTS optimization performance and integration."""
    
    def __init__(self):
        self.config = AppConfig()
        self.service = GeminiAssessmentService(self.config)
        self.results = []
        
    def create_perfect_assessment(self) -> AssessmentResult:
        """Create an assessment with no errors."""
        return AssessmentResult(specific_errors=[])
    
    def create_error_assessment(self, num_errors: int = 2) -> AssessmentResult:
        """Create an assessment with specific errors."""
        errors = []
        test_words = ["vest", "best", "test", "rest", "nest", "west", "pest", "fest"]
        
        for i in range(min(num_errors, len(test_words))):
            errors.append(SpecificError(
                word=test_words[i],
                issue=f"You said '{test_words[i]}' incorrectly",
                suggestion=f"Try saying '{test_words[i]}' more clearly",
                severity="minor"
            ))
        
        return AssessmentResult(specific_errors=errors)
    
    def measure_latency(self, assessment: AssessmentResult) -> Tuple[float, bytes]:
        """Measure TTS generation latency in milliseconds."""
        start_time = time.perf_counter()
        audio_bytes = self.service.generate_tts_narration(assessment)
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        return latency_ms, audio_bytes
    
    def test_perfect_reading_latency(self) -> bool:
        """Test 1: Perfect reading should play within 50ms."""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: Perfect Reading Latency (<50ms)")
        logger.info("="*80)
        
        assessment = self.create_perfect_assessment()
        latency_ms, audio_bytes = self.measure_latency(assessment)
        
        passed = latency_ms < 50 and audio_bytes is not None
        
        logger.info(f"Latency: {latency_ms:.2f}ms")
        logger.info(f"Audio generated: {len(audio_bytes) if audio_bytes else 0} bytes")
        logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
        
        self.results.append({
            "test": "Perfect Reading Latency",
            "target": "<50ms",
            "actual": f"{latency_ms:.2f}ms",
            "passed": passed
        })
        
        return passed
    
    def test_cache_miss_latency(self) -> bool:
        """Test 2: New errors (cache miss) should generate within 2 seconds."""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: Cache Miss Latency (<2000ms)")
        logger.info("="*80)
        
        # Clear cache to ensure miss
        cache_dir = Path(self.config.tts_cache_dir)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Cache cleared to force cache miss")
        
        # Reinitialize service to reset cache
        self.service = GeminiAssessmentService(self.config)
        
        assessment = self.create_error_assessment(num_errors=2)
        latency_ms, audio_bytes = self.measure_latency(assessment)
        
        passed = latency_ms < 2000 and audio_bytes is not None
        
        logger.info(f"Latency: {latency_ms:.2f}ms")
        logger.info(f"Audio generated: {len(audio_bytes) if audio_bytes else 0} bytes")
        logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
        
        self.results.append({
            "test": "Cache Miss Latency",
            "target": "<2000ms",
            "actual": f"{latency_ms:.2f}ms",
            "passed": passed
        })
        
        return passed
    
    def test_cache_hit_latency(self) -> bool:
        """Test 3: Repeated errors (cache hit) should return within 100ms."""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: Cache Hit Latency (<100ms)")
        logger.info("="*80)
        
        # First call to populate cache
        assessment = self.create_error_assessment(num_errors=2)
        logger.info("Warming up cache with first call...")
        self.service.generate_tts_narration(assessment)
        
        # Second call should hit cache
        logger.info("Testing cache hit with identical assessment...")
        latency_ms, audio_bytes = self.measure_latency(assessment)
        
        passed = latency_ms < 100 and audio_bytes is not None
        
        logger.info(f"Latency: {latency_ms:.2f}ms")
        logger.info(f"Audio generated: {len(audio_bytes) if audio_bytes else 0} bytes")
        logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
        
        self.results.append({
            "test": "Cache Hit Latency",
            "target": "<100ms",
            "actual": f"{latency_ms:.2f}ms",
            "passed": passed
        })
        
        return passed
    
    def test_fallback_without_manifest(self) -> bool:
        """Test 4: Fallback to legacy TTS when manifest.json is missing."""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: Fallback Behavior (Missing Manifest)")
        logger.info("="*80)
        
        manifest_path = Path(self.config.tts_manifest_path)
        backup_path = manifest_path.with_suffix('.json.backup')
        
        try:
            # Backup and remove manifest
            if manifest_path.exists():
                shutil.copy(manifest_path, backup_path)
                manifest_path.unlink()
                logger.info(f"Removed manifest: {manifest_path}")
            
            # Reinitialize service (should fall back to legacy)
            self.service = GeminiAssessmentService(self.config)
            
            # Test with perfect reading
            assessment = self.create_perfect_assessment()
            latency_ms, audio_bytes = self.measure_latency(assessment)
            
            passed = audio_bytes is not None
            
            logger.info(f"Latency: {latency_ms:.2f}ms (legacy TTS)")
            logger.info(f"Audio generated: {len(audio_bytes) if audio_bytes else 0} bytes")
            logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
            
            self.results.append({
                "test": "Fallback Without Manifest",
                "target": "Audio generated",
                "actual": f"{len(audio_bytes) if audio_bytes else 0} bytes",
                "passed": passed
            })
            
            return passed
            
        finally:
            # Restore manifest
            if backup_path.exists():
                shutil.copy(backup_path, manifest_path)
                backup_path.unlink()
                logger.info(f"Restored manifest: {manifest_path}")
            
            # Reinitialize service with restored manifest
            self.service = GeminiAssessmentService(self.config)
    
    def test_cache_size_limit(self, num_assessments: int = 100) -> bool:
        """Test 5: Cache directory stays under 500MB limit."""
        logger.info("\n" + "="*80)
        logger.info(f"TEST 5: Cache Size Limit (<500MB after {num_assessments} assessments)")
        logger.info("="*80)
        
        # Clear cache
        cache_dir = Path(self.config.tts_cache_dir)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Reinitialize service
        self.service = GeminiAssessmentService(self.config)
        
        logger.info(f"Generating {num_assessments} assessments with varied errors...")
        
        for i in range(num_assessments):
            # Create varied assessments to populate cache
            num_errors = (i % 3) + 1  # 1-3 errors
            assessment = self.create_error_assessment(num_errors=num_errors)
            
            # Vary the error content slightly
            for j, error in enumerate(assessment.specific_errors):
                error.word = f"word{i}_{j}"
                error.issue = f"Issue {i}_{j}"
                error.suggestion = f"Suggestion {i}_{j}"
            
            self.service.generate_tts_narration(assessment)
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i + 1}/{num_assessments} assessments")
        
        # Calculate cache size
        cache_size_bytes = sum(
            f.stat().st_size for f in cache_dir.rglob('*') if f.is_file()
        )
        cache_size_mb = cache_size_bytes / (1024 * 1024)
        
        passed = cache_size_mb < 500
        
        logger.info(f"Cache size: {cache_size_mb:.2f}MB")
        logger.info(f"Cache location: {cache_dir}")
        logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
        
        self.results.append({
            "test": "Cache Size Limit",
            "target": "<500MB",
            "actual": f"{cache_size_mb:.2f}MB",
            "passed": passed
        })
        
        return passed
    
    def test_cache_hit_rate(self, num_assessments: int = 100) -> bool:
        """Test 6: Cache hit rate >70% after warm-up period."""
        logger.info("\n" + "="*80)
        logger.info(f"TEST 6: Cache Hit Rate (>70% after {num_assessments} assessments)")
        logger.info("="*80)
        
        # Clear cache
        cache_dir = Path(self.config.tts_cache_dir)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Reinitialize service
        self.service = GeminiAssessmentService(self.config)
        
        # Create a pool of common error patterns
        common_patterns = [
            self.create_error_assessment(num_errors=1),
            self.create_error_assessment(num_errors=2),
            self.create_error_assessment(num_errors=3),
        ]
        
        # Warm up cache with common patterns
        logger.info("Warming up cache with common patterns...")
        for pattern in common_patterns:
            self.service.generate_tts_narration(pattern)
        
        # Track cache hits/misses
        cache_hits = 0
        cache_misses = 0
        
        logger.info(f"Running {num_assessments} assessments with repeated patterns...")
        
        for i in range(num_assessments):
            # 80% of the time, use a common pattern (should hit cache)
            # 20% of the time, use a new pattern (will miss cache)
            if i % 5 == 0:
                # New pattern
                assessment = self.create_error_assessment(num_errors=(i % 3) + 1)
                for j, error in enumerate(assessment.specific_errors):
                    error.word = f"unique_word_{i}_{j}"
                    error.issue = f"Unique issue {i}_{j}"
                    error.suggestion = f"Unique suggestion {i}_{j}"
            else:
                # Common pattern
                assessment = common_patterns[i % len(common_patterns)]
            
            # Measure latency to infer cache hit/miss
            latency_ms, _ = self.measure_latency(assessment)
            
            # Heuristic: <200ms likely cache hit, >500ms likely cache miss
            if latency_ms < 200:
                cache_hits += 1
            else:
                cache_misses += 1
            
            if (i + 1) % 10 == 0:
                current_hit_rate = (cache_hits / (cache_hits + cache_misses)) * 100
                logger.info(f"  Progress: {i + 1}/{num_assessments} | Hit rate: {current_hit_rate:.1f}%")
        
        total_requests = cache_hits + cache_misses
        hit_rate = (cache_hits / total_requests) * 100 if total_requests > 0 else 0
        
        passed = hit_rate > 70
        
        logger.info(f"Cache hits: {cache_hits}")
        logger.info(f"Cache misses: {cache_misses}")
        logger.info(f"Hit rate: {hit_rate:.1f}%")
        logger.info(f"Status: {'✓ PASS' if passed else '✗ FAIL'}")
        
        self.results.append({
            "test": "Cache Hit Rate",
            "target": ">70%",
            "actual": f"{hit_rate:.1f}%",
            "passed": passed
        })
        
        return passed
    
    def print_summary(self):
        """Print summary of all test results."""
        logger.info("\n" + "="*80)
        logger.info("VALIDATION SUMMARY")
        logger.info("="*80)
        
        for result in self.results:
            status = "✓ PASS" if result["passed"] else "✗ FAIL"
            logger.info(f"{status} | {result['test']}")
            logger.info(f"       Target: {result['target']}, Actual: {result['actual']}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["passed"])
        
        logger.info("="*80)
        logger.info(f"TOTAL: {passed_tests}/{total_tests} tests passed")
        logger.info("="*80)
        
        return passed_tests == total_tests


def main():
    """Run all validation tests."""
    logger.info("Starting TTS Optimization Validation")
    logger.info("="*80)
    
    validator = PerformanceValidator()
    
    try:
        # Run all tests
        validator.test_perfect_reading_latency()
        validator.test_cache_miss_latency()
        validator.test_cache_hit_latency()
        validator.test_fallback_without_manifest()
        
        # These tests are more intensive - can be run separately if needed
        # validator.test_cache_size_limit(num_assessments=100)
        # validator.test_cache_hit_rate(num_assessments=100)
        
        # Print summary
        all_passed = validator.print_summary()
        
        if all_passed:
            logger.info("\n✓ All validation tests passed!")
            return 0
        else:
            logger.warning("\n✗ Some validation tests failed. Review results above.")
            return 1
            
    except Exception as e:
        logger.error(f"Validation failed with error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
