# Security Hardening Implementation Plan

## Overview
Implement missing security features identified in SECURITY_ANALYSIS.md without breaking existing functionality.

## Items to Implement (in priority order)

### 1. FRONTEND-BACKEND STATE SYNCHRONIZATION [CRITICAL - HIGH PRIORITY]
**Problem**: App relies on localStorage without validating session with server

**Implementation**:
- Create `useSessionValidator` hook that calls `/me` on app initialization
- Validate local user matches server user
- Clear state and redirect on mismatch or 401
- Add to App.tsx or AuthLayout to run on all protected routes

**Files to modify**:
- `frontend/src/hooks/useSessionValidator.ts` (NEW)
- `frontend/src/layouts/AuthLayout.tsx` (MODIFY)
- `frontend/src/App.tsx` (if needed)

**Testing**:
- Verify app calls /me on load
- Verify logout on 401
- Verify no UI flash of wrong user

---

### 2. SECURITY EVENT LOGGING [HIGH PRIORITY]
**Problem**: No visibility into security events like failed session validations

**Implementation**:
- Create security logger module
- Log events: session_validation_failed, session_binding_mismatch, suspicious_ip_change
- Store in database for audit trail
- Add endpoint for viewing security logs (admin only)

**Files to modify**:
- `backend/app/auth/security_logger.py` (NEW)
- `backend/app/auth/models.py` (ADD SecurityEvent model)
- `backend/app/auth/service.py` (ADD logging calls)
- `backend/app/auth/dependencies.py` (ADD logging on validation failure)

**Testing**:
- Verify events are logged to database
- Verify no PII in logs (hash IP addresses)

---

### 3. SUBNET-BASED IP VALIDATION [MEDIUM PRIORITY]
**Problem**: Strict IP validation will log out mobile users when IP changes

**Implementation**:
- Modify `_ip_binding_hash` to store both full IP and /24 subnet
- Implement "strict" vs "lenient" validation mode
- Use lenient mode for mobile users (check subnet match)
- Add user preference or auto-detect mobile

**Files to modify**:
- `backend/app/auth/service.py` (MODIFY ip validation logic)
- `backend/app/auth/models.py` (ADD validation_mode field)

**Testing**:
- Test IP change within same /24 subnet - should pass
- Test IP change to different subnet - should fail
- Test mobile user experience

---

### 4. ACCEPT-LANGUAGE FINGERPRINTING [LOW PRIORITY]
**Problem**: Missing additional fingerprint signal

**Implementation**:
- Add accept-language header to session binding
- Include in validation logic
- Low weight in scoring (10-20%)

**Files to modify**:
- `backend/app/auth/service.py` (ADD language_hash)

---

## Implementation Order

### Phase 1: Critical Fixes (State Sync)
1. Implement useSessionValidator hook
2. Add to AuthLayout
3. Test with session replay scenario

### Phase 2: Observability (Security Logging)
1. Create SecurityEvent model
2. Add security_logger module
3. Log validation failures in auth service

### Phase 3: UX Improvement (IP Subnet)
1. Modify IP validation to support subnet matching
2. Add detection for mobile users
3. Test with various network scenarios

### Phase 4: Additional Hardening (Optional)
1. Add Accept-Language fingerprinting
2. Add rate limiting on /me endpoint
3. Add suspicious activity notifications

## Risk Mitigation

### Backward Compatibility
- All changes are additive
- Existing sessions will continue to work
- Database migrations will be reversible

### Testing Strategy
1. Unit tests for new functions
2. Integration tests for session flow
3. Manual testing for mobile scenarios
4. Security testing for replay attacks

### Rollback Plan
- Keep old validation logic as fallback
- Feature flags for new behaviors
- Monitor error rates after deployment

## Validation Checklist

After each phase:
- [ ] All existing tests pass
- [ ] New tests added and passing
- [ ] Manual testing completed
- [ ] No console errors
- [ ] Mobile experience verified
- [ ] Session replay attack blocked
