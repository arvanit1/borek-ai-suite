/**
 * AT-14 logo injection — fills the master pic placeholder from the Borek wordmark asset.
 *
 * White wordmark on dark slides; navy wordmark on light slides. Placement comes from
 * branding tokens. Layouts must not add their own logo image.
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import type PptxGenJS from "pptxgenjs";

import { BorekBranding, computeBrandingLayout } from "../tokens/branding.js";

export const LOGO_PLACEHOLDER = BorekBranding.logo.placeholderName;

const assetsDir = join(fileURLToPath(new URL(".", import.meta.url)), "..", "assets");

/** White wordmark for dark cover/closing fields. */
export const BOREK_LOGO_ON_DARK_PATH = join(assetsDir, "logo.png");

/** Navy wordmark for light content slides. */
export const BOREK_LOGO_ON_LIGHT_PATH = join(assetsDir, "logo-on-light.png");

/** Default path kept for existing tests — light-slide wordmark. */
export const BOREK_LOGO_PATH = BOREK_LOGO_ON_LIGHT_PATH;

export type LogoVariant = "light" | "dark";

export function logoAssetPath(variant: LogoVariant = "light"): string {
  return variant === "dark" ? BOREK_LOGO_ON_DARK_PATH : BOREK_LOGO_ON_LIGHT_PATH;
}

export function addLogo(slide: PptxGenJS.Slide, variant: LogoVariant = "light"): void {
  const path = logoAssetPath(variant);
  if (!existsSync(path)) {
    throw new Error(`Borek logo asset is missing at ${path}`);
  }

  const logo = computeBrandingLayout().logo;
  slide.addImage({
    path,
    placeholder: LOGO_PLACEHOLDER,
    x: logo.x,
    y: logo.y,
    w: logo.w,
    h: logo.h,
  });
}
