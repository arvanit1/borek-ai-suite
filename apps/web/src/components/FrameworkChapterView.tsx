"use client";

import { FrameworkNestedValue } from "@/components/FrameworkNestedValue";
import { SourceRefBadge } from "@/components/SourceRefBadge";
import {
  isBlockTypeKey,
  isEditableContentKey,
  sourceRefsForFactDisplay,
} from "@/lib/frameworkEvidence";
import { updateChapterStringBody } from "@/lib/frameworkEdit";
import { updateChapterBodyValue } from "@/lib/frameworkNestedEdit";
import type { FrameworkChapter } from "@/lib/frameworkTypes";

function ChapterSourceRefs({ chapter }: { chapter: FrameworkChapter }) {
  const refs = sourceRefsForFactDisplay(chapter);
  return (
    <div className="framework-fact-sources" aria-label="Source references">
      {refs.length > 0 ? (
        refs.map((refItem, refIndex) => (
          <SourceRefBadge key={`${chapter.chapter_id}-ref-${refIndex}`} refItem={refItem} />
        ))
      ) : (
        <p className="framework-fact-sources-empty">No cited source for this chapter.</p>
      )}
    </div>
  );
}

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
            bodyBlocks.map((block, blockIndex) => {
              const factRefs = sourceRefsForFactDisplay(chapter, block);
              const blockType = typeof block.block === "string" ? block.block : null;
              return (
                <article
                  key={`${chapter.chapter_id}-${blockIndex}`}
                  className="framework-fact-block"
                  data-testid="framework-fact-block"
                >
                  {blockType ? <p className="framework-fact-kind">{blockType}</p> : null}
                  <div className="framework-fact-fields">
                    {Object.entries(block)
                      .filter(([fieldKey]) => isEditableContentKey(fieldKey) && !isBlockTypeKey(fieldKey))
                      .map(([fieldKey, fieldValue]) => (
                        <FrameworkNestedValue
                          key={fieldKey}
                          id={`${chapter.chapter_id}-${blockIndex}-${fieldKey}`}
                          label={fieldKey}
                          value={fieldValue}
                          editable={editable}
                          onChange={(next) =>
                            onChange(updateChapterBodyValue(chapter, blockIndex, fieldKey, next))
                          }
                        />
                      ))}
                  </div>
                  <div
                    className="framework-fact-sources"
                    aria-label="Source references for this fact"
                    data-testid="framework-fact-sources"
                  >
                    {factRefs.length > 0 ? (
                      factRefs.map((refItem, refIndex) => (
                        <SourceRefBadge
                          key={`${chapter.chapter_id}-${blockIndex}-${refItem.conversation_id}-${refItem.excerpt_pointer}-${refIndex}`}
                          refItem={refItem}
                        />
                      ))
                    ) : (
                      <p className="framework-fact-sources-empty">No cited source for this fact.</p>
                    )}
                  </div>
                </article>
              );
            })
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
            <ChapterSourceRefs chapter={chapter} />
          </div>
        )}
      </div>
    </section>
  );
}
