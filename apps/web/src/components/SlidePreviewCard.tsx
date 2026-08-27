"use client";

import { useEffect, useState } from "react";

import { fetchSlidePreviewBlob } from "@/lib/api";

interface SlidePreviewCardProps {
  accessToken: string;
  slideIndex: number;
  layoutId: string;
  previewPath: string;
}

export function SlidePreviewCard({
  accessToken,
  slideIndex,
  layoutId,
  previewPath,
}: SlidePreviewCardProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    async function loadPreview() {
      setError(null);
      try {
        const blob = await fetchSlidePreviewBlob(accessToken, previewPath);
        objectUrl = URL.createObjectURL(blob);
        if (active) {
          setImageUrl(objectUrl);
        }
      } catch (loadError) {
        if (active) {
          setImageUrl(null);
          setError(loadError instanceof Error ? loadError.message : "Preview failed.");
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

  return (
    <article className="deck-slide-card">
      <div className="deck-slide-preview" data-testid={`deck-slide-${slideIndex}`}>
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt={`Slide ${slideIndex + 1} preview`} />
        ) : error ? (
          <div className="deck-slide-fallback">{error}</div>
        ) : (
          <div className="deck-slide-fallback">Loading preview…</div>
        )}
      </div>
      <footer className="deck-slide-meta">
        <strong>Slide {slideIndex + 1}</strong>
        <code>{layoutId}</code>
      </footer>
    </article>
  );
}
