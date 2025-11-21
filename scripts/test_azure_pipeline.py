#!/usr/bin/env python3
"""Test script for the Azure Speech + Gemini pronunciation assessment pipeline.

Usage:
    # Test full pipeline with a WAV file
    python scripts/test_azure_pipeline.py --audio sample.wav --text "The cat is on the mat"

    # Test Azure connection only
    python scripts/test_azure_pipeline.py --test-connection

    # Test with default sample (if available)
    python scripts/test_azure_pipeline.py
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_azure_connection():
    """Test Azure Speech service connection."""
    print("Testing Azure Speech connection...")

    from services.azure_speech_service import AzureSpeechConfig
    from exceptions import ConfigurationError

    try:
        config = AzureSpeechConfig.from_env()
        print(f"  Region: {config.speech_region}")
        print(f"  Language: {config.language_code}")
        print("  Azure credentials loaded successfully!")
        return True
    except ConfigurationError as e:
        print(f"  ERROR: {e}")
        return False


def test_azure_assessment(audio_path: str, reference_text: str):
    """Test Azure Speech pronunciation assessment with a WAV file."""
    print("\nTesting Azure pronunciation assessment...")
    print(f"  Audio: {audio_path}")
    print(f"  Text: {reference_text}")

    from services.azure_speech_service import (
        assess_pronunciation_with_azure,
        extract_assessment_summary,
    )

    # Read audio file
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    print(f"  Audio size: {len(audio_bytes)} bytes")

    # Call Azure
    result = assess_pronunciation_with_azure(
        audio_bytes=audio_bytes,
        reference_text=reference_text,
    )

    print("\n  Azure Response:")
    print(f"    Recognition Status: {result.get('RecognitionStatus')}")

    if result.get("RecognitionStatus") == "Success":
        summary = extract_assessment_summary(result)
        scores = summary["overall_scores"]

        print("\n  Overall Scores:")
        print(f"    Pronunciation: {scores['pronunciation_score']:.1f}")
        print(f"    Accuracy:      {scores['accuracy_score']:.1f}")
        print(f"    Fluency:       {scores['fluency_score']:.1f}")
        print(f"    Completeness:  {scores['completeness_score']:.1f}")
        print(f"    Prosody:       {scores['prosody_score']:.1f}")

        print(f"\n  Recognized Text: {summary['display_text']}")

        if summary["words"]:
            print("\n  Word-level Details:")
            for word in summary["words"]:
                error = (
                    f" ({word['error_type']})" if word["error_type"] != "None" else ""
                )
                print(f"    - {word['word']}: {word['accuracy_score']:.1f}{error}")

    return result


def test_full_pipeline(audio_path: str, reference_text: str):
    """Test the full Azure + Gemini pipeline."""
    print(f"\n{'=' * 60}")
    print("Testing Full Pipeline (Azure + Gemini)")
    print(f"{'=' * 60}")

    from config import AppConfig
    from services.gemini_service import AssessmentService

    # Initialize service
    config = AppConfig()
    service = AssessmentService(config=config)

    # Read audio file
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    print(f"Audio: {audio_path} ({len(audio_bytes)} bytes)")
    print(f"Reference: {reference_text}\n")

    # Run assessment
    result = service.assess_pronunciation(
        audio_data_bytes=audio_bytes,
        expected_sentence_text=reference_text,
    )

    print("Results:")
    print(f"  Summary: {result.summary_text}")
    print("\n  Overall Scores:")
    print(f"    Pronunciation: {result.overall_scores.pronunciation:.1f}")
    print(f"    Accuracy:      {result.overall_scores.accuracy:.1f}")
    print(f"    Fluency:       {result.overall_scores.fluency:.1f}")
    print(f"    Completeness:  {result.overall_scores.completeness:.1f}")
    print(f"    Prosody:       {result.overall_scores.prosody:.1f}")

    if result.word_level_feedback:
        print(f"\n  Feedback ({len(result.word_level_feedback)} items):")
        for fb in result.word_level_feedback:
            print(f"    - [{fb.severity}] {fb.word}: {fb.issue}")
            print(f"      Suggestion: {fb.suggestion}")

    if result.prosody_feedback:
        print(f"\n  Prosody Feedback: {result.prosody_feedback}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Test Azure Speech + Gemini pronunciation assessment pipeline"
    )
    parser.add_argument(
        "--audio",
        type=str,
        help="Path to WAV audio file (16kHz mono PCM)",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="The cat is on the mat",
        help="Reference sentence (default: 'The cat is on the mat')",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Only test Azure connection, don't run assessment",
    )
    parser.add_argument(
        "--azure-only",
        action="store_true",
        help="Only test Azure (skip Gemini analysis)",
    )

    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    # Test connection
    if not test_azure_connection():
        print("\nFailed to connect to Azure. Please check your credentials.")
        sys.exit(1)

    if args.test_connection:
        print("\nConnection test passed!")
        sys.exit(0)

    # Check for audio file
    if not args.audio:
        # Look for sample audio files
        sample_paths = [
            "sample.wav",
            "test.wav",
            "assets/sample.wav",
            "scripts/sample.wav",
        ]
        for path in sample_paths:
            if os.path.exists(path):
                args.audio = path
                break

    if not args.audio or not os.path.exists(args.audio):
        print("\nNo audio file provided or found.")
        print(
            "Usage: python scripts/test_azure_pipeline.py --audio path/to/audio.wav --text 'Your sentence'"
        )
        sys.exit(1)

    # Run tests
    if args.azure_only:
        test_azure_assessment(args.audio, args.text)
    else:
        test_full_pipeline(args.audio, args.text)

    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()
