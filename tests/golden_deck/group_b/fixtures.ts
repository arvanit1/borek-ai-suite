/**
 * JJ-22: Approved Group B golden-deck reference fixtures.
 * Schematic PNGs are token-derived from the live layout compute functions.
 */

import { PNG } from "pngjs";

import { computeTimelineLayout } from "../../../apps/renderer/design_system/components/addTimeline.js";
import { BorekSlide } from "../../../apps/renderer/design_system/tokens/branding.js";
import { BorekColors } from "../../../apps/renderer/design_system/tokens/colors.js";
import { computeProcessFlow01Layout } from "../../../apps/renderer/layouts/group_b/renderProcessFlow01.js";
import { computeMilestones01Layout } from "../../../apps/renderer/layouts/group_b/renderMilestones01.js";
import { computeTeamFte01Layout } from "../../../apps/renderer/layouts/group_b/renderTeamFte01.js";
import {
  buildTimeline01PhaseItems,
  computeTimeline01Layout,
} from "../../../apps/renderer/layouts/group_b/renderTimeline01.js";

export const GROUP_B_GOLDEN_WIDTH = 320;
export const GROUP_B_GOLDEN_HEIGHT = 180;
export const GROUP_B_GOLDEN_SCALE = GROUP_B_GOLDEN_HEIGHT / BorekSlide.heightInches;

export const GROUP_B_GOLDEN_FILES = [
  "process_flow_01.png",
  "timeline_01.png",
  "milestones_01.png",
  "team_fte_01.png",
] as const;

export type GroupBGoldenFile = (typeof GROUP_B_GOLDEN_FILES)[number];

type Rgb = [number, number, number];

function hexToRgb(hex: string): Rgb {
  const normalized = hex.replace("#", "");
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

function fillRect(
  png: PNG,
  x: number,
  y: number,
  width: number,
  height: number,
  rgb: Rgb,
): void {
  const x0 = Math.max(0, Math.floor(x));
  const y0 = Math.max(0, Math.floor(y));
  const x1 = Math.min(png.width, Math.ceil(x + width));
  const y1 = Math.min(png.height, Math.ceil(y + height));
  for (let row = y0; row < y1; row += 1) {
    for (let col = x0; col < x1; col += 1) {
      const offset = (row * png.width + col) * 4;
      png.data[offset] = rgb[0];
      png.data[offset + 1] = rgb[1];
      png.data[offset + 2] = rgb[2];
      png.data[offset + 3] = 255;
    }
  }
}

function px(inches: number): number {
  return inches * GROUP_B_GOLDEN_SCALE;
}

function blankSlide(): PNG {
  const png = new PNG({ width: GROUP_B_GOLDEN_WIDTH, height: GROUP_B_GOLDEN_HEIGHT });
  fillRect(png, 0, 0, png.width, png.height, hexToRgb(BorekColors.background));
  fillRect(png, px(0.65), px(1.1), px(12.0), px(0.28), hexToRgb(BorekColors.text));
  fillRect(png, px(0.65), px(1.45), px(2.4), px(0.08), hexToRgb(BorekColors.primary));
  fillRect(png, px(0.65), px(7.15), px(12.0), px(0.04), hexToRgb(BorekColors.border));
  return png;
}

function fillInchRect(
  png: PNG,
  rect: { x: number; y: number; w: number; h: number },
  rgb: Rgb,
  inset = 0,
): void {
  fillRect(
    png,
    px(rect.x) + inset,
    px(rect.y) + inset,
    Math.max(1, px(rect.w) - inset * 2),
    Math.max(1, px(rect.h) - inset * 2),
    rgb,
  );
}

export function buildProcessFlow01Png(): PNG {
  const png = blankSlide();
  const layout = computeProcessFlow01Layout(true, 5);
  for (const card of layout.cards) {
    fillInchRect(png, card, hexToRgb(BorekColors.border));
    fillInchRect(png, card, hexToRgb(BorekColors.background), 2);
    fillRect(
      png,
      px(card.x + card.w / 2) - 4,
      px(card.y) + 4,
      8,
      8,
      hexToRgb(BorekColors.primary),
    );
  }
  return png;
}

export function buildTimeline01Png(): PNG {
  const png = blankSlide();
  const phases = [
    { id: "p1", name: "Discover", description: "Confirm scope" },
    { id: "p2", name: "Build", description: "Matching rules" },
    { id: "p3", name: "Pilot", description: "Controlled run" },
    { id: "p4", name: "Handover", description: "Operations" },
  ];
  const milestones = [
    { phaseId: "p1", date: "Week 2" },
    { phaseId: "p2", date: "Week 6" },
    { phaseId: "p3", date: "Week 10" },
    { phaseId: "p4", date: "Week 14" },
  ];
  const items = buildTimeline01PhaseItems(phases, milestones);
  const layout = computeTimeline01Layout(true, items, 4);
  const geometry = computeTimelineLayout(layout.timeline, items);
  fillInchRect(png, layout.timeline, hexToRgb(BorekColors.border));
  for (const phase of geometry.phases) {
    fillInchRect(png, phase.segment, hexToRgb(BorekColors.primary));
  }
  for (const anchor of layout.milestoneAnchors) {
    fillRect(png, px(anchor.x) - 3, px(anchor.y) - 3, 6, 6, hexToRgb(BorekColors.primary));
    fillRect(png, px(anchor.x) - 8, px(anchor.y) + 6, 16, 6, hexToRgb(BorekColors.mutedText));
  }
  return png;
}

export function buildMilestones01Png(): PNG {
  const png = blankSlide();
  const layout = computeMilestones01Layout(true, 4, ["Week 2", "Week 6", "Week 10", "Week 14"]);
  fillRect(
    png,
    px(layout.trackFrom.x),
    px(layout.trackFrom.y) - 1,
    px(layout.trackTo.x - layout.trackFrom.x),
    2,
    hexToRgb(BorekColors.border),
  );
  for (const anchor of layout.anchors) {
    fillRect(png, px(anchor.x) - 4, px(anchor.y) - 4, 8, 8, hexToRgb(BorekColors.primary));
    fillRect(png, px(anchor.x) - 10, px(anchor.y) + 8, 20, 8, hexToRgb(BorekColors.mutedText));
  }
  for (const card of layout.descriptions) {
    fillInchRect(png, card, hexToRgb(BorekColors.border));
    fillInchRect(png, card, hexToRgb(BorekColors.background), 2);
  }
  return png;
}

export function buildTeamFte01Png(): PNG {
  const png = blankSlide();
  const layout = computeTeamFte01Layout(true, 4, 3);
  for (const card of layout.roles) {
    fillInchRect(png, card, hexToRgb(BorekColors.border));
    fillInchRect(png, card, hexToRgb(BorekColors.background), 2);
    fillRect(
      png,
      px(card.x) + 4,
      px(card.y) + 4,
      Math.max(8, px(card.w) - 8),
      8,
      hexToRgb(BorekColors.text),
    );
  }
  for (const stat of layout.summary) {
    fillInchRect(png, stat, hexToRgb(BorekColors.primary));
  }
  return png;
}

export function buildGroupBGoldenPng(fileName: GroupBGoldenFile): PNG {
  switch (fileName) {
    case "process_flow_01.png":
      return buildProcessFlow01Png();
    case "timeline_01.png":
      return buildTimeline01Png();
    case "milestones_01.png":
      return buildMilestones01Png();
    case "team_fte_01.png":
      return buildTeamFte01Png();
  }
}
