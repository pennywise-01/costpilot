/// <reference types="vite/client" />

/**
 * Type-safe access to `import.meta.env` for the env vars CostPilot
 * actually uses. Vite exposes any `VITE_*` variable from `.env` files
 * to the bundle at build time.
 */
interface ImportMetaEnv {
  /**
   * AWS principal CostPilot's backend assumes roles AS. Used by the
   * onboarding wizard to render a CloudFormation Quick-Create URL with
   * the correct trust principal pre-filled.
   */
  readonly VITE_COSTPILOT_AWS_PRINCIPAL_ARN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
