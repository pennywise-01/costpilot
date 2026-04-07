/**
 * Browser fingerprinting utility for session security.
 * 
 * This creates a unique fingerprint based on browser characteristics
 * that can differentiate between different browser sessions even
 * when they share the same IP address (e.g., localhost testing).
 */

export interface BrowserFingerprint {
  screenResolution: string;
  colorDepth: number;
  timezone: string;
  language: string;
  platform: string;
  hardwareConcurrency: number;
  deviceMemory?: number;
}

/**
 * Generate a browser fingerprint from available browser features.
 * This helps differentiate between different browser sessions on the same machine.
 */
export function generateFingerprint(): BrowserFingerprint {
  return {
    screenResolution: `${window.screen.width}x${window.screen.height}`,
    colorDepth: window.screen.colorDepth,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language || (navigator as any).userLanguage || 'en',
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency || 0,
    deviceMemory: (navigator as any).deviceMemory,
  };
}

/**
 * Get fingerprint as a string for hashing.
 */
export function getFingerprintString(): string {
  const fp = generateFingerprint();
  return JSON.stringify(fp);
}

/**
 * Get a simple hash of the fingerprint for cookie storage.
 */
export function getFingerprintHash(): string {
  const str = getFingerprintString();
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash.toString(16);
}

/**
 * Store fingerprint in localStorage for comparison.
 */
export function storeFingerprint(): void {
  try {
    localStorage.setItem('browser_fp', getFingerprintString());
  } catch {
    // Ignore storage errors
  }
}

/**
 * Check if current fingerprint matches stored one.
 * Returns true if they match or if no stored fingerprint exists.
 */
export function verifyFingerprint(): boolean {
  try {
    const stored = localStorage.getItem('browser_fp');
    if (!stored) return true;
    return stored === getFingerprintString();
  } catch {
    return true;
  }
}
