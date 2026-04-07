import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { authApi } from '@/api/auth';
import { ROUTES } from '@/utils/routes';

interface SessionValidatorState {
  isValidating: boolean;
  isValid: boolean | null;
  error: string | null;
}

/**
 * Validates the current session with the server on mount.
 * 
 * This hook addresses the security issue where the app relies on localStorage
 * for authentication state without verifying with the server. If someone copies
 * cookies to another browser (session replay attack), this hook will detect
 * the mismatch and force logout.
 * 
 * Security features:
 * - Validates session with /me endpoint on app initialization
 * - Compares server user ID with localStorage user ID
 * - Forces logout on mismatch or 401
 * - Prevents UI from showing stale/wrong user data
 */
export const useSessionValidator = (): SessionValidatorState => {
  const navigate = useNavigate();
  const { user, logout, setUser } = useAuthStore();
  const [state, setState] = useState<SessionValidatorState>({
    isValidating: true,
    isValid: null,
    error: null,
  });

  useEffect(() => {
    const validateSession = async () => {
      // If no user in localStorage, nothing to validate
      if (!user) {
        setState({ isValidating: false, isValid: false, error: null });
        return;
      }

      try {
        // Call /me endpoint to validate session with server
        const { data: serverUser } = await authApi.getMe();

        // Check if server user matches local user
        if (serverUser.id !== user.id) {
          // Security issue: User mismatch detected
          console.error('Session validation failed: User ID mismatch', {
            localUserId: user.id,
            serverUserId: serverUser.id,
          });
          
          // Clear local state and redirect to login
          logout();
          setState({
            isValidating: false,
            isValid: false,
            error: 'Session invalid. Please log in again.',
          });
          navigate(ROUTES.LOGIN, { replace: true });
          return;
        }

        // Session is valid, refresh user data from server
        setUser(serverUser);
        setState({ isValidating: false, isValid: true, error: null });
      } catch (error) {
        // Handle 401 or other errors
        console.error('Session validation failed:', error);
        
        logout();
        setState({
          isValidating: false,
          isValid: false,
          error: 'Session expired. Please log in again.',
        });
        navigate(ROUTES.LOGIN, { replace: true });
      }
    };

    validateSession();
  }, [user?.id]); // Only re-run if user ID changes

  return state;
};

export default useSessionValidator;
