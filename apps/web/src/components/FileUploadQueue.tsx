"use client";

import { useRef, useState } from "react";

import {
  ABC_SYSTEMS_Q2_SAMPLE_FILENAME,
  ABC_SYSTEMS_Q2_SAMPLE_TRANSCRIPT,
} from "@/lib/abcSystemsQ2Transcript";
import { ALLOWED_TRANSCRIPT_EXTENSIONS } from "@/lib/transcriptFormats";
import {
  createQueueItems,
  getUploadableItems,
  hasUploadableItems,
  removeQueueItem,
  statusLabel,
  type TranscriptQueueItem,
} from "@/lib/uploadQueue";

interface FileUploadQueueProps {
  items: TranscriptQueueItem[];
  uploadDisabled?: boolean;
  onItemsChange: (items: TranscriptQueueItem[]) => void;
  onUpload: (items: TranscriptQueueItem[]) => Promise<void>;
}

function statusClassName(status: TranscriptQueueItem["status"]): string {
  return `status-badge status-${status}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileUploadQueue({
  items,
  uploadDisabled = false,
  onItemsChange,
  onUpload,
}: FileUploadQueueProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadableCount = getUploadableItems(items).length;
  const canSubmit = hasUploadableItems(items);
  const settled =
    items.length > 0 &&
    !canSubmit &&
    !busy &&
    !items.some((item) => item.status === "uploading" || item.status === "error");
  const sampleQueued = items.some((item) => item.fileName === ABC_SYSTEMS_Q2_SAMPLE_FILENAME);

  function addFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) {
      return;
    }
    const nextItems = createQueueItems(Array.from(fileList));
    onItemsChange([...items, ...nextItems]);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function handleRemove(id: string) {
    onItemsChange(removeQueueItem(items, id));
  }

  function handleAddSampleTranscript() {
    if (sampleQueued) {
      return;
    }
    const file = new File(
      [ABC_SYSTEMS_Q2_SAMPLE_TRANSCRIPT],
      ABC_SYSTEMS_Q2_SAMPLE_FILENAME,
      { type: "text/plain" },
    );
    onItemsChange([...items, ...createQueueItems([file])]);
  }

  async function handleUploadClick() {
    const uploadable = getUploadableItems(items);
    if (uploadable.length === 0) {
      return;
    }
    if (uploadDisabled) {
      setError("Create an opportunity before uploading files to the API.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onUpload(uploadable);
    } catch (uploadError) {
      const message =
        uploadError instanceof Error ? uploadError.message : "Upload failed.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  const fileInput = (
    <input
      ref={inputRef}
      type="file"
      multiple
      hidden
      accept={ALLOWED_TRANSCRIPT_EXTENSIONS.join(",")}
      disabled={busy}
      onChange={(event) => addFiles(event.target.files)}
    />
  );

  return (
    <div className={`file-queue${settled ? " file-queue-settled" : ""}`}>
      {settled ? (
        <div className="file-queue-toolbar">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            Add files
          </button>
          {fileInput}
        </div>
      ) : (
        <div
          className={`upload-dropzone${dragActive ? " upload-dropzone-active" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragActive(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            addFiles(event.dataTransfer.files);
          }}
        >
          <div className="upload-dropzone-icon" aria-hidden="true">
            ↑
          </div>
          <p className="upload-dropzone-title">Drop transcript files here</p>
          <p className="upload-dropzone-subtitle">
            or browse from your computer · {ALLOWED_TRANSCRIPT_EXTENSIONS.join(", ")}
          </p>
          <div className="upload-dropzone-actions">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
            >
              Browse files
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy || sampleQueued}
              onClick={handleAddSampleTranscript}
            >
              Add sample transcript
            </button>
          </div>
          {fileInput}
        </div>
      )}

      {items.length > 0 ? (
        <div className="file-table-wrap">
          <table className="file-table">
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">Status</th>
                <th scope="col" className="file-table-actions-col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className={`file-table-row file-table-row-${item.status}`}>
                  <td>
                    <div className="file-name">{item.fileName}</div>
                    {item.errorMessage ? (
                      <div className="file-detail file-detail-error">{item.errorMessage}</div>
                    ) : (
                      <div className="file-detail">{formatFileSize(item.file.size)}</div>
                    )}
                  </td>
                  <td>
                    <span className={statusClassName(item.status)}>{statusLabel(item.status)}</span>
                  </td>
                  <td className="file-table-actions-col">
                    {item.status === "success" ? null : (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        disabled={busy || item.status === "uploading"}
                        onClick={() => handleRemove(item.id)}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {error ? <div className="alert alert-error">{error}</div> : null}

      {canSubmit || busy ? (
        <div className="file-queue-footer">
          <p className="file-queue-note">
            Only files marked <strong>Ready</strong> are submitted. Unsupported formats never leave
            your browser.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || !canSubmit}
            onClick={handleUploadClick}
          >
            {busy
              ? "Uploading…"
              : uploadableCount > 0
                ? `Upload ${uploadableCount} file${uploadableCount === 1 ? "" : "s"}`
                : "Upload files"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
