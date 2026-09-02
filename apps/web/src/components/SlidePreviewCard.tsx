"use client";

import React, { useEffect, useState } from "react";

import { fetchSlidePreviewBlob } from "@/lib/api";
import { alternativeLayouts, formatLayoutLabel, PREVIEW_UNAVAILABLE_LABEL } from "@/lib/presentationReady";

interface SlidePreviewCardProps {
  accessToken: string;
  slideId: string;
  slideIndex: number;
  layoutId: string;
  previewPath: string | null;
  featured?: boolean;
  busy?: boolean;
  canEdit?: boolean;
  onSelect?: () => void;
  onRegenerate?: (slideId: string) => void;
  onChangeLayout?: (slideId: string, layoutId: string) => void;
}

export function SlidePreviewCard({
  accessToken,
  slideId,
  slideIndex,
  layoutId,
  previewPath,
  featured = false,
  busy = false,
  canEdit = false,
  onSelect,
  onRegenerate,
  onChangeLayout,
}: SlidePreviewCardProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const layoutOptions = alternativeLayouts(layoutId);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    async function loadPreview() {
      setError(null);
      setImageUrl(null);
      if (!previewPath) {
        setError(PREVIEW_UNAVAILABLE_LABEL);
        return;
      }
      try {
        const blob = await fetchSlidePreviewBlob(accessToken, previewPath);
        objectUrl = URL.createObjectURL(blob);
        if (active) {
          setImageUrl(objectUrl);
        }
      } catch {
        if (active) {
          setImageUrl(null);
          setError(PREVIEW_UNAVAILABLE_LABEL);
        }
      }
    }

    void loadPreview();

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [accessToken, previewPath]);

  const preview = (
    <div className="deck-slide-preview" data-testid={`deck-slide-${slideIndex}`}>
      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={imageUrl} alt={`Slide ${slideIndex + 1} preview`} />
      ) : (
        <div className="deck-slide-fallback">{error ?? "Loading preview…"}</div>
      )}
    </div>
  );

  return (
    <article className={featured ? "deck-slide-card deck-slide-card-featured" : "deck-slide-card"}>
      {onSelect ? (
        <button type="button" className="deck-slide-select" onClick={onSelect} disabled={busy}>
          {preview}
        </button>
      ) : (
        preview
      )}
      <footer className="deck-slide-meta">
        <strong>Slide {slideIndex + 1}</strong>
        <span>{formatLayoutLabel(layoutId)}</span>
        {canEdit ? (
          <div className="deck-slide-actions">
            {onRegenerate ? (
              <button
                type="button"
                className="btn btn-secondary"
                disabled={busy}
                onClick={() => onRegenerate(slideId)}
              >
                Regenerate slide
              </button>
            ) : null}
            {onChangeLayout && layoutOptions.length > 0 ? (
              <label className="deck-slide-layout-picker">
                <span>Change layout</span>
                <select
                  value={layoutId}
                  disabled={busy}
                  onChange={(event) => {
                    const nextLayout = event.target.value;
                    if (nextLayout && nextLayout !== layoutId) {
                      onChangeLayout(slideId, nextLayout);
                    }
                  }}
                >
                  <option value={layoutId}>{formatLayoutLabel(layoutId)}</option>
                  {layoutOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
        ) : null}
      </footer>
    </article>
  );
}
