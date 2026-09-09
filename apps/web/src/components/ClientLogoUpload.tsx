"use client";

import React, { useEffect, useState } from "react";

import {
  deleteClientLogo,
  fetchClientLogoContent,
  getClientLogoMetadata,
  uploadClientLogo,
  type ClientLogoMetadata,
} from "@/lib/api";
import {
  clientLogoErrorMessage,
  isMissingClientLogoError,
} from "@/lib/apiErrors";
import {
  CLIENT_LOGO_ACCEPT,
  validateClientLogoFile,
} from "@/lib/clientIntake";

interface ClientLogoUploadProps {
  accessToken: string;
  opportunityId: string;
  clientName?: string | null;
}

export function ClientLogoUpload({
  accessToken,
  opportunityId,
  clientName,
}: ClientLogoUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<ClientLogoMetadata | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setSelectedFile(null);
    setMetadata(null);
    setPreviewUrl(null);
    setError(null);
    setNotice(null);
  }, [accessToken, opportunityId]);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    async function loadPreview() {
      setPreviewUrl(null);
      if (selectedFile) {
        objectUrl = URL.createObjectURL(selectedFile);
        if (active) {
          setPreviewUrl(objectUrl);
        } else {
          URL.revokeObjectURL(objectUrl);
          objectUrl = null;
        }
        return;
      }
      try {
        setMetadata(null);
        const currentMetadata = await getClientLogoMetadata(accessToken, opportunityId);
        const blob = await fetchClientLogoContent(accessToken, opportunityId);
        objectUrl = URL.createObjectURL(blob);
        if (active) {
          setMetadata(currentMetadata);
          setPreviewUrl(objectUrl);
        } else {
          URL.revokeObjectURL(objectUrl);
          objectUrl = null;
        }
      } catch (loadError) {
        if (active && !isMissingClientLogoError(loadError)) {
          setError(clientLogoErrorMessage(loadError));
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
  }, [accessToken, opportunityId, selectedFile]);

  function chooseFile(file: File | null) {
    setError(null);
    setNotice(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const validation = validateClientLogoFile(file);
    if (!validation.ok) {
      setSelectedFile(null);
      setError(validation.reason ?? "Choose another client logo.");
      return;
    }
    setSelectedFile(file);
  }

  async function saveLogo() {
    if (!selectedFile) {
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await uploadClientLogo(accessToken, opportunityId, selectedFile);
      setMetadata(saved);
      setSelectedFile(null);
      setNotice("Client logo saved.");
    } catch (saveError) {
      setError(clientLogoErrorMessage(saveError));
    } finally {
      setBusy(false);
    }
  }

  async function removeLogo() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await deleteClientLogo(accessToken, opportunityId);
      setMetadata(null);
      setSelectedFile(null);
      setPreviewUrl(null);
      setNotice("Client logo removed.");
    } catch (removeError) {
      setError(clientLogoErrorMessage(removeError));
    } finally {
      setBusy(false);
    }
  }

  const wordmark = (clientName ?? "").trim() || "Client name";

  return (
    <section className="client-logo-upload" aria-labelledby="client-logo-heading">
      <div className="client-logo-copy">
        <div className="client-logo-title-row">
          <h3 id="client-logo-heading">Client logo</h3>
          <span className="optional-label">Optional</span>
        </div>
        <p>Shown on the cover and closing, bottom-right, beside the Borek mark.</p>
        <p className="client-logo-requirements">PNG, JPEG, or WebP. 5 MiB maximum.</p>
        {error ? <div className="alert alert-error">{error}</div> : null}
        {notice ? <p className="client-logo-notice" role="status">{notice}</p> : null}
        <div className="client-logo-actions">
          <label className="btn btn-secondary" htmlFor="client_logo_file">
            {metadata || selectedFile ? "Choose another logo" : "Choose client logo"}
          </label>
          <input
            id="client_logo_file"
            className="visually-hidden"
            type="file"
            accept={CLIENT_LOGO_ACCEPT}
            disabled={busy}
            onChange={(event) => {
              chooseFile(event.target.files?.[0] ?? null);
              event.target.value = "";
            }}
          />
          {selectedFile ? (
            <button type="button" className="btn btn-primary" disabled={busy} onClick={saveLogo}>
              {busy ? "Saving..." : "Save logo"}
            </button>
          ) : null}
          {metadata && !selectedFile ? (
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={removeLogo}>
              {busy ? "Removing..." : "Remove logo"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="client-logo-card" data-testid="client-logo-preview">
        <span className="client-logo-card-kicker">Cover</span>
        <footer className="client-logo-card-footer">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="client-logo-borek" src="/logo.webp" alt="Borek" />
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="client-logo-client" src={previewUrl} alt="Client logo preview" />
          ) : (
            <span className="client-logo-wordmark">{wordmark}</span>
          )}
        </footer>
      </div>
    </section>
  );
}
