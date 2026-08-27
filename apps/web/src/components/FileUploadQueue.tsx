"use client";

import { useRef, useState } from "react";

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

  return (
    <div className="file-queue">
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
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept={ALLOWED_TRANSCRIPT_EXTENSIONS.join(",")}
          disabled={busy}
          onChange={(event) => addFiles(event.target.files)}
        />
      </div>

      {items.length === 0 ? (
        <div className="upload-empty-state">
          <p>No files queued yet. Invalid extensions are marked rejected immediately — they never leave your browser.</p>
        </div>
      ) : (
        <div className="file-table-wrap">
          <table className="file-table">
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">Size</th>
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
                    ) : item.transcriptId ? (
                      <div className="file-detail">ID {item.transcriptId}</div>
                    ) : null}
                  </td>
                  <td className="file-size">{formatFileSize(item.file.size)}</td>
                  <td>
                    <span className={statusClassName(item.status)}>{statusLabel(item.status)}</span>
                  </td>
                  <td className="file-table-actions-col">
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={busy || item.status === "uploading"}
                      onClick={() => handleRemove(item.id)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error ? <div className="alert alert-error">{error}</div> : null}

      <div className="file-queue-footer">
        <p className="file-queue-note">
          Only files marked <strong>Ready</strong> are submitted. Unsupported formats never leave
          your browser.
        </p>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !hasUploadableItems(items)}
          onClick={handleUploadClick}
        >
          {busy
            ? "Uploading…"
            : uploadableCount > 0
              ? `Upload ${uploadableCount} file${uploadableCount === 1 ? "" : "s"}`
              : "Upload files"}
        </button>
      </div>
    </div>
  );
}
