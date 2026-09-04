-- AT-59: versioned Borek knowledge metadata and structured facts.
-- Source files remain in the approved enterprise repository. Normal users can
-- read approved public/internal facts but cannot ingest or modify the corpus.

CREATE TABLE IF NOT EXISTS knowledge_corpus_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corpus_key TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'approved', 'retired')),
  owner TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  approved_at TIMESTAMPTZ,
  UNIQUE (corpus_key, version)
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  corpus_version_id UUID NOT NULL
    REFERENCES knowledge_corpus_versions(id) ON DELETE CASCADE,
  document_key TEXT NOT NULL,
  document_type TEXT NOT NULL,
  source_uri TEXT NOT NULL,
  source_version TEXT NOT NULL,
  classification TEXT NOT NULL
    CHECK (classification IN ('public', 'internal', 'client_confidential', 'restricted')),
  effective_from DATE,
  effective_to DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (corpus_version_id, document_key, source_version)
);

CREATE TABLE IF NOT EXISTS knowledge_facts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL
    REFERENCES knowledge_documents(id) ON DELETE CASCADE,
  fact_key TEXT NOT NULL,
  kind TEXT NOT NULL
    CHECK (kind IN ('service', 'pricing', 'staffing', 'reference')),
  service_key TEXT,
  query_key TEXT NOT NULL,
  statement TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  search_terms TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, fact_key),
  UNIQUE (query_key, document_id)
);

CREATE INDEX IF NOT EXISTS knowledge_corpus_status_idx
  ON knowledge_corpus_versions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS knowledge_documents_corpus_idx
  ON knowledge_documents(corpus_version_id);
CREATE INDEX IF NOT EXISTS knowledge_facts_query_idx
  ON knowledge_facts(query_key);
CREATE INDEX IF NOT EXISTS knowledge_facts_service_kind_idx
  ON knowledge_facts(service_key, kind);

ALTER TABLE knowledge_corpus_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_facts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated_read_approved_corpus_versions"
  ON knowledge_corpus_versions;
CREATE POLICY "authenticated_read_approved_corpus_versions"
  ON knowledge_corpus_versions
  FOR SELECT
  TO authenticated
  USING (status = 'approved');

DROP POLICY IF EXISTS "authenticated_read_approved_knowledge_documents"
  ON knowledge_documents;
CREATE POLICY "authenticated_read_approved_knowledge_documents"
  ON knowledge_documents
  FOR SELECT
  TO authenticated
  USING (
    classification IN ('public', 'internal')
    AND corpus_version_id IN (
      SELECT id FROM knowledge_corpus_versions WHERE status = 'approved'
    )
  );

DROP POLICY IF EXISTS "authenticated_read_approved_knowledge_facts"
  ON knowledge_facts;
CREATE POLICY "authenticated_read_approved_knowledge_facts"
  ON knowledge_facts
  FOR SELECT
  TO authenticated
  USING (
    document_id IN (
      SELECT d.id
      FROM knowledge_documents d
      INNER JOIN knowledge_corpus_versions c ON c.id = d.corpus_version_id
      WHERE c.status = 'approved'
        AND d.classification IN ('public', 'internal')
    )
  );
