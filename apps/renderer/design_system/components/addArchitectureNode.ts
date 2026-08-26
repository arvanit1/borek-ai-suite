/**
 * AT-29: Labeled architecture-diagram node component (technical plan v2 §17.1).
 *
 * Numbered circle badge + title/description card for ARCHITECTURE_01 (MS-16).
 * Composes addNumberBadge (AT-24) and addContentCard (AT-22).
 * Layout renderers must call this — never define their own architecture-node styling.
 */

import type PptxGenJS from "pptxgenjs";

import { addContentCard, type ContentCardRect } from "./addContentCard.js";
import {
  addNumberBadge,
  numberBadgeDiameter,
  type NumberBadgeRect,
} from "./addNumberBadge.js";

export interface ArchitectureNodeRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Semantic architecture node — aligns with ARCHITECTURE_01 SlideSpec component item. */
export interface ArchitectureNodeContent {
  number: number;
  title: string;
  description: string;
}

export interface ArchitectureNodeLayout {
  badge: NumberBadgeRect;
  card: ContentCardRect;
}

/** Badge diameter — reuses AT-24 token-derived default. */
export function architectureNodeBadgeSize(): number {
  return numberBadgeDiameter();
}

/**
 * Place the numbered badge centered on the node box top-left corner;
 * card fills the caller-supplied position rectangle.
 */
export function computeArchitectureNodeLayout(rect: ArchitectureNodeRect): ArchitectureNodeLayout {
  const badgeSize = architectureNodeBadgeSize();
  const half = badgeSize / 2;

  return {
    badge: {
      x: rect.x - half,
      y: rect.y - half,
      w: badgeSize,
      h: badgeSize,
    },
    card: {
      x: rect.x,
      y: rect.y,
      w: rect.w,
      h: rect.h,
    },
  };
}

/**
 * Render a single numbered architecture node at the given slide coordinates.
 *
 * @example
 * addArchitectureNode(slide, { x: 1.5, y: 2.0, w: 3.2, h: 1.4 }, {
 *   number: 1,
 *   title: "AP Mailbox",
 *   description: "Source of invoices, read-only",
 * });
 */
export function addArchitectureNode(
  slide: PptxGenJS.Slide,
  position: ArchitectureNodeRect,
  node: ArchitectureNodeContent,
): void {
  const layout = computeArchitectureNodeLayout(position);

  addContentCard(slide, layout.card, {
    title: node.title,
    description: node.description,
  });
  addNumberBadge(slide, layout.badge, node.number);
}
