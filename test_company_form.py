#!/usr/bin/env python
"""
Test script for Company form zip validation integration (without database)
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'horilla.settings')
django.setup()

from base.forms import validate_zip_code
from django.core.exceptions import ValidationError

def test_zip_validation_directly():
    """Test zip validation function directly"""
    
    print("=" * 60)
    print("DIRECT ZIP VALIDATION TEST")
    print("=" * 60)
    
    # Valid zip codes to test
    valid_zips = [
        "12345",      # US
        "A1A1A1",     # Canada
        "SW1A1AA",    # UK
        "394210",     # India
        "1234AB",     # Netherlands
    ]
    
    # Invalid zip codes to test
    invalid_zips = [
        "12",                    # Too short
        "12345678901",          # Too long
        "12345@",               # Invalid character
        "123456789",            # Sequential (9 digits)
        "",                     # Empty
    ]
    
    print("\nTesting VALID zip codes:")
    valid_count = 0
    for zip_code in valid_zips:
        try:
            validate_zip_code(zip_code)
            print(f"✓ PASS: {zip_code} - Validation passed")
            valid_count += 1
        except ValidationError as e:
            print(f"✗ FAIL: {zip_code} - Validation failed: {e}")
    
    print(f"\nValid zip codes passed: {valid_count}/{len(valid_zips)}")
    
    print("\nTesting INVALID zip codes:")
    invalid_count = 0
    for zip_code in invalid_zips:
        try:
            validate_zip_code(zip_code)
            print(f"✗ FAIL: {zip_code} - Should be invalid but passed")
        except ValidationError as e:
            print(f"✓ PASS: {zip_code} - Correctly rejected: {e}")
            invalid_count += 1
    
    print(f"\nInvalid zip codes correctly rejected: {invalid_count}/{len(invalid_zips)}")
    
    total_tests = len(valid_zips) + len(invalid_zips)
    total_passed = valid_count + invalid_count
    success_rate = (total_passed / total_tests) * 100
    
    print(f"\nOverall validation success rate: {total_passed}/{total_tests} ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("🎉 ALL VALIDATION TESTS PASSED!")
    elif success_rate >= 90:
        print("✅ Most validation tests passed.")
    else:
        print("⚠️  Validation needs improvement.")
    
    print("=" * 60)

if __name__ == "__main__":
    test_zip_validation_directly()