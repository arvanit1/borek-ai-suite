CREATE TABLE IF NOT EXISTS public.knowledge_model_checkpoints (
    generation_job_id UUID NOT NULL REFERENCES public.generation_jobs(id) ON DELETE CASCADE,
    transcript_id UUID NOT NULL REFERENCES public.transcripts(id) ON DELETE CASCADE,
    opportunity_id UUID NOT NULL REFERENCES public.opportunities(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    knowledge_model_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (generation_job_id, transcript_id)
);

ALTER TABLE public.knowledge_model_checkpoints ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.knowledge_model_checkpoints FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.knowledge_model_checkpoints TO service_role;
