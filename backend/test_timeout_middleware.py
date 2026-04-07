"""Test script to verify timeout middleware path matching logic."""

def get_timeout_for_path(path: str, endpoint_timeouts: dict, default_timeout: float = 30.0) -> float:
    """Replicated logic from TimeoutMiddleware._get_timeout_for_path"""
    path_parts = path.split('/')
    
    # Check for /api/v1/organizations/{org_id}/expenses pattern
    if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "expenses":
        return 90.0
    
    # Check for /api/v1/organizations/{org_id}/resources pattern  
    if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "resources":
        return 120.0
        
    # Check for /api/v1/organizations/{org_id}/recommendations pattern
    if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "recommendations":
        return 60.0
        
    # Check for /api/v1/organizations/{org_id}/cloud-accounts pattern
    if len(path_parts) >= 6 and path_parts[3] == "organizations" and path_parts[5] == "cloud-accounts":
        return 45.0
    
    # Find the most specific matching prefix for other paths
    matching_prefixes = [
        (prefix, timeout)
        for prefix, timeout in endpoint_timeouts.items()
        if path.startswith(prefix)
    ]

    if matching_prefixes:
        # Return the longest (most specific) matching prefix
        return max(matching_prefixes, key=lambda x: len(x[0]))[1]

    return default_timeout


def test_timeout_matching():
    """Test that nested organization endpoints get correct timeouts."""
    
    endpoint_timeouts = {
        "/api/v1/auth": 10.0,
        "/api/v1/organizations": 10.0,
        "/api/v1/pools": 15.0,
        "/api/v1/expenses": 90.0,
        "/api/v1/resources": 120.0,
        "/api/v1/recommendations": 60.0,
        "/api/v1/rules": 15.0,
        "/api/v1/cloud-accounts": 45.0,
        "/api/v1/export": 300.0,
        "/api/v1/scheduler": 30.0,
        "/api/v1/users": 15.0,
        "/api/v1/rbac": 15.0,
    }
    
    test_cases = [
        # (path, expected_timeout, description)
        ("/api/v1/organizations", 10.0, "Base organizations endpoint"),
        ("/api/v1/organizations/123", 10.0, "Single org endpoint"),
        ("/api/v1/organizations/123/expenses/summary", 90.0, "Org expenses endpoint"),
        ("/api/v1/organizations/123/expenses/breakdown", 90.0, "Org expenses breakdown"),
        ("/api/v1/organizations/456/resources", 120.0, "Org resources endpoint"),
        ("/api/v1/organizations/789/recommendations", 60.0, "Org recommendations endpoint"),
        ("/api/v1/organizations/abc/cloud-accounts", 45.0, "Org cloud-accounts endpoint"),
        ("/api/v1/organizations/xyz/users", 10.0, "Org users endpoint (should use base org timeout)"),
        ("/api/v1/organizations/org123/pools", 10.0, "Org pools endpoint (should use base org timeout)"),
        ("/api/v1/expenses", 90.0, "Direct expenses endpoint"),
        ("/api/v1/resources", 120.0, "Direct resources endpoint"),
        ("/api/v1/auth/login", 10.0, "Auth endpoint"),
    ]
    
    print("Testing Timeout Middleware Path Matching")
    print("=" * 70)
    
    all_passed = True
    for path, expected_timeout, description in test_cases:
        actual_timeout = get_timeout_for_path(path, endpoint_timeouts)
        status = "[PASS]" if actual_timeout == expected_timeout else "[FAIL]"
        
        if actual_timeout != expected_timeout:
            all_passed = False
            
        print(f"{status} | {description}")
        print(f"       Path: {path}")
        print(f"       Expected: {expected_timeout}s, Got: {actual_timeout}s")
        print()
    
    print("=" * 70)
    if all_passed:
        print("[SUCCESS] All tests passed!")
        return 0
    else:
        print("[FAILED] Some tests failed!")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(test_timeout_matching())
