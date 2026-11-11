/**
 * The consent line ADR-0039 requires on onboarding: what we store and where.
 *
 * Keep this the only copy of the wording. If it changes, bump CONSENT_VERSION here AND the
 * backend's CONSENT_VERSION (backend/src/api/onboarding.py, PR #13) so stored records name the
 * text the owner actually saw.
 */
export const CONSENT_VERSION = "2026-11-phase2-v1";

export const CONSENT_TEXT =
  "I agree that Catalyst may store my business details and my contact details, and the names and " +
  "phone numbers of people who call or message my business, on servers in Singapore, to run my front " +
  "desk. No medical details are collected.";
