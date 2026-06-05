from __future__ import annotations

from app.core.config import settings


def get_ai_catalog() -> dict:
    providers = _model_providers()
    vector_stores = _vector_stores()
    search_providers = _search_providers()
    capabilities = _capabilities()
    return {
        "version": settings.app_version,
        "summary": {
            "model_providers": len(providers),
            "vector_stores": len(vector_stores),
            "web_search_providers": len(search_providers),
            "capabilities": len(capabilities),
            "active_model_provider": settings.model_provider,
            "active_vector_store": settings.vector_store_provider,
        },
        "model_providers": providers,
        "vector_stores": vector_stores,
        "web_search_providers": search_providers,
        "capabilities": capabilities,
        "recommended_next": [
            "Configurar a chave do Gemini no ambiente local para usar Gemini como inteligencia principal online.",
            "Adicionar embeddings e um vector store persistente para RAG sem depender apenas de FTS.",
            "Implementar streaming para reduzir a sensacao de lentidao.",
            "Criar UI local segura para configurar provider sem salvar chave no banco.",
        ],
    }


def _model_providers() -> list[dict]:
    return [
        _provider("gemini", "Cloud API", "Google Gemini generateContent", "supported", False, ["GEMINI_MODEL"], "Provider principal online com fallback local para Ollama."),
        _provider("ollama", "Local", "Ollama HTTP API", "supported", True, ["NEXUSTI_OLLAMA_URL", "NEXUSTI_OLLAMA_MODEL"], "Fallback local offline."),
        _provider("openai-responses", "Cloud API", "OpenAI Responses API", "supported", False, ["NEXUSTI_OPENAI_API_KEY", "NEXUSTI_OPENAI_MODEL"], "Provider forte para agente, tool calling e respostas gerais."),
        _provider("openai-compatible", "Gateway/API", "OpenAI-compatible Chat Completions", "supported", False, ["NEXUSTI_OPENAI_COMPAT_BASE_URL", "NEXUSTI_OPENAI_COMPAT_API_KEY", "NEXUSTI_OPENAI_COMPAT_MODEL"], "Serve para OpenRouter, Groq, Together, Fireworks, DeepInfra, LocalAI, LM Studio e outros endpoints compativeis."),
        _provider("litellm-proxy", "Gateway", "LiteLLM Proxy", "planned", True, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Boa ponte para muitos providers sem criar adapter para cada um."),
        _provider("llama-cpp-server", "Local", "llama.cpp OpenAI-compatible server", "planned", True, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Opcao leve para modelos locais quantizados."),
        _provider("vllm", "Local/Servidor", "vLLM OpenAI-compatible server", "planned", True, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Bom para servidor com GPU e alta vazao."),
        _provider("localai", "Local/Servidor", "LocalAI OpenAI-compatible API", "planned", True, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Alternativa self-hosted com API compativel."),
        _provider("lm-studio", "Local", "LM Studio local server", "planned", False, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Facil para usuario final rodar modelo local com endpoint compativel."),
        _provider("text-generation-inference", "Servidor", "Hugging Face TGI", "planned", True, ["NEXUSTI_OPENAI_COMPAT_BASE_URL"], "Opcao para hospedar modelos abertos em producao."),
        _provider("anthropic", "Cloud API", "Anthropic Messages API", "catalog", False, [], "Exige adapter proprio; manter no catalogo para fase multi-provider."),
        _provider("mistral", "Cloud API", "Mistral API", "catalog", False, [], "Provider europeu com modelos comerciais e abertos."),
        _provider("cohere", "Cloud API", "Cohere Chat/Embed/Rerank", "catalog", False, [], "Interessante para rerank e busca semantica."),
    ]


def _vector_stores() -> list[dict]:
    return [
        _store("sqlite-fts5", "SQLite FTS5", "supported", True, "Busca textual local leve, ja usada no Nexus."),
        _store("chroma", "ChromaDB", "planned", True, "Bom para dev local e RAG simples."),
        _store("qdrant", "Qdrant", "planned", True, "Forte para producao self-hosted com filtros e payloads."),
        _store("faiss", "FAISS", "planned", True, "Excelente biblioteca local de similaridade; precisa camada de persistencia."),
        _store("pgvector", "PostgreSQL + pgvector", "planned", True, "Boa escolha quando ja existe Postgres e dados relacionais."),
        _store("milvus", "Milvus", "planned", True, "Voltado a escala maior e workloads vetoriais pesados."),
        _store("weaviate", "Weaviate", "planned", True, "Vector DB com schema e opcoes hibridas."),
        _store("lancedb", "LanceDB", "planned", True, "Armazenamento local/embutido interessante para datasets e multimodal."),
        _store("opensearch", "OpenSearch Vector", "catalog", True, "Bom quando a empresa ja usa busca textual e logs."),
        _store("elasticsearch", "Elasticsearch Vector", "catalog", False, "Opcao madura para busca hibrida em stacks existentes."),
        _store("redis", "Redis Vector", "catalog", True, "Util para cache semantico e baixa latencia."),
        _store("neo4j", "Neo4j Knowledge Graph", "catalog", False, "Camada de grafo para relacoes, inventario e historico tecnico."),
    ]


def _search_providers() -> list[dict]:
    return [
        {"name": "searxng", "status": "supported", "privacy": "high", "env": ["NEXUSTI_SEARXNG_URL"]},
        {"name": "duckduckgo_html", "status": "supported", "privacy": "medium", "env": ["NEXUSTI_WEB_PROVIDER"]},
        {"name": "brave_search", "status": "planned", "privacy": "medium", "env": []},
        {"name": "kagi", "status": "planned", "privacy": "medium", "env": []},
        {"name": "tavily", "status": "planned", "privacy": "medium", "env": []},
        {"name": "serpapi", "status": "planned", "privacy": "low", "env": []},
        {"name": "bing", "status": "planned", "privacy": "medium", "env": []},
        {"name": "jina_reader", "status": "planned", "privacy": "medium", "env": []},
        {"name": "exa", "status": "planned", "privacy": "medium", "env": []},
    ]


def _capabilities() -> list[dict]:
    return [
        {"name": "streaming", "status": "planned", "why": "Mostra resposta parcial e reduz sensacao de lentidao."},
        {"name": "tool_calling", "status": "partial", "why": "Ferramentas existem, falta chamada estruturada por LLM."},
        {"name": "human_confirmation", "status": "supported", "why": "Obrigatorio para acoes sensiveis."},
        {"name": "rag_hybrid", "status": "planned", "why": "Combinar FTS, vetor e rerank melhora busca local."},
        {"name": "semantic_cache", "status": "planned", "why": "Reduz custo e latencia em perguntas repetidas."},
        {"name": "reranking", "status": "planned", "why": "Ordena melhor evidencias de RAG/web."},
        {"name": "prompt_injection_guard", "status": "partial", "why": "Web fetch ja e read-only; falta detector dedicado."},
        {"name": "provider_failover", "status": "partial", "why": "Router escolhe provider; falta retry/failover configuravel."},
        {"name": "rate_limits", "status": "planned", "why": "Necessario para mobile e rede local."},
        {"name": "token_budgeting", "status": "planned", "why": "Evita prompts gigantes e respostas lentas."},
        {"name": "voice", "status": "catalog", "why": "Fase futura com STT/TTS local ou API."},
        {"name": "pwa_mobile", "status": "planned", "why": "Acesso mobile seguro sem app nativo no curto prazo."},
    ]


def _provider(key: str, kind: str, name: str, status: str, open_source: bool, env: list[str], note: str) -> dict:
    return {"key": key, "kind": kind, "name": name, "status": status, "open_source": open_source, "env": env, "note": note}


def _store(key: str, name: str, status: str, open_source: bool, note: str) -> dict:
    return {"key": key, "name": name, "status": status, "open_source": open_source, "note": note}
