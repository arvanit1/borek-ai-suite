"use client";

import { SourceRefBadge } from "@/components/SourceRefBadge";
import {
  updateChapterBodyField,
  updateChapterStringBody,
} from "@/lib/frameworkEdit";
import type { FrameworkChapter } from "@/lib/frameworkTypes";

interface FrameworkChapterViewProps {
  chapter: FrameworkChapter;
  editable: boolean;
  regenerating?: boolean;
  onChange: (chapter: FrameworkChapter) => void;
  onRegenerate?: () => void;
}

export function FrameworkChapterView({
  chapter,
  editable,
  regenerating = false,
  onChange,
  onRegenerate,
}: FrameworkChapterViewProps) {
  const bodyBlocks = Array.isArray(chapter.body) ? chapter.body : null;

  return (
    <section className="framework-chapter">
      <header className="framework-chapter-header">
        <div>
          <p className="framework-chapter-id">Chapter {chapter.chapter_id}</p>
          <h3>{chapter.title}</h3>
        </div>
        {onRegenerate ? (
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!editable || regenerating}
            onClick={onRegenerate}
          >
            {regenerating ? "Regenerating…" : "Regenerate chapter"}
          </button>
        ) : null}
      </header>

      <div className="framework-chapter-body">
        {bodyBlocks ? (
          bodyBlocks.length === 0 ? (
            <p className="upload-hint">No structured facts in this chapter yet.</p>
          ) : (
          bodyBlocks.map((block, blockIndex) => (
            <article key={`${chapter.chapter_id}-${blockIndex}`} className="framework-fact-block">
              <div className="framework-fact-fields">
                {Object.entries(block).map(([fieldKey, fieldValue]) => (
                  <div key={fieldKey} className="form-field">
                    <label htmlFor={`${chapter.chapter_id}-${blockIndex}-${fieldKey}`}>
                      {fieldKey}
                    </label>
                    <input
                      id={`${chapter.chapter_id}-${blockIndex}-${fieldKey}`}
                      value={String(fieldValue ?? "")}
                      disabled={!editable}
                      onChange={(event) =>
                        onChange(
                          updateChapterBodyField(
                            chapter,
                            blockIndex,
                            fieldKey,
                            event.target.value,
                          ),
                        )
                      }
                    />
                  </div>
                ))}
              </div>
              {chapter.source_refs.length > 0 ? (
                <div className="framework-fact-sources" aria-label="Source references for this fact">
                  {chapter.source_refs.map((refItem, refIndex) => (
                    <SourceRefBadge key={`${chapter.chapter_id}-${blockIndex}-${refIndex}`} refItem={refItem} />
                  ))}
                </div>
              ) : null}
            </article>
          ))
          )
        ) : (
          <div className="form-field">
            <label htmlFor={`${chapter.chapter_id}-body`}>Body</label>
            <textarea
              id={`${chapter.chapter_id}-body`}
              rows={8}
              value={typeof chapter.body === "string" ? chapter.body : ""}
              disabled={!editable}
              onChange={(event) => onChange(updateChapterStringBody(chapter, event.target.value))}
            />
            {chapter.source_refs.length > 0 ? (
              <div className="framework-fact-sources" aria-label="Source references">
                {chapter.source_refs.map((refItem, refIndex) => (
                  <SourceRefBadge key={`${chapter.chapter_id}-ref-${refIndex}`} refItem={refItem} />
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
