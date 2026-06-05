from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.agent.memory_stores.sqlite_memory import init_agent_storage
from app.agent.memory_stores.vector_memory import VectorMemoryStore
from app.core.config import settings
from app.core.runtime import is_cloud
from app.core.logging_db import get_connection


INITIAL_KNOWLEDGE = [
    {
        "title": "Spooler de impressao com erro",
        "category": "printer",
        "tags": ["spooler", "impressora", "fila", "windows"],
        "content": "Quando o spooler falha, primeiro colete status do servico, verifique fila de impressao, reinicie o spooler com permissao elevada apenas apos confirmacao e valide se a impressora volta a aceitar trabalhos.",
    },
    {
        "title": "Limpeza segura da fila de impressao",
        "category": "printer",
        "tags": ["fila", "spool", "print queue"],
        "content": "A limpeza de fila deve parar o spooler, limpar arquivos temporarios de spool e iniciar o servico novamente. Esta acao e sensivel e exige confirmacao e permissao elevada.",
    },
    {
        "title": "Driver de impressora travado",
        "category": "printer",
        "tags": ["driver", "impressora", "windows"],
        "content": "Driver travado costuma aparecer como impressora offline, fila presa ou erro ao imprimir. Priorize verificar porta, driver correto do fabricante, status do spooler e conflitos com driver antigo.",
    },
    {
        "title": "Impressora offline",
        "category": "printer",
        "tags": ["offline", "rede", "porta"],
        "content": "Para impressora offline, verifique cabo/rede, IP atual, porta TCP/IP configurada, SNMP, fila pausada e se ha trabalhos presos. Em rede, confirme ping e interface correta.",
    },
    {
        "title": "Brother pedindo recolocar toner",
        "category": "printer",
        "tags": ["brother", "toner", "cilindro"],
        "content": "Em Brother, mensagem para recolocar toner com toner novo pode indicar cartucho mal encaixado, chip/engrenagem de reset, tampa mal fechada, toner incompativel, sensor sujo ou necessidade de reset conforme modelo. Nao force procedimento sem modelo exato.",
    },
    {
        "title": "Brother reset de toner e cilindro",
        "category": "printer",
        "tags": ["brother", "reset", "toner", "cilindro"],
        "content": "Reset de toner/cilindro varia por modelo. Use apenas procedimento documentado pelo fabricante ou manual tecnico confiavel. Antes, confirme modelo, consumivel correto e ausencia de obstrucao fisica.",
    },
    {
        "title": "Epson L3250 luzes piscando",
        "category": "printer",
        "tags": ["epson", "l3250", "luzes"],
        "content": "Na Epson L3250, luzes piscando podem indicar papel preso, tampa aberta, almofada de tinta no fim, erro de scanner ou inicializacao. Verifique padrao das luzes e consulte manual oficial.",
    },
    {
        "title": "Erro 0x80300024 instalacao Windows",
        "category": "windows",
        "tags": ["0x80300024", "instalacao", "disco"],
        "content": "O erro 0x80300024 geralmente envolve conflito de discos, ordem de boot, particao alvo, modo UEFI/Legacy ou cabos. Desconectar discos extras e selecionar corretamente o disco alvo costuma reduzir risco.",
    },
    {
        "title": "SMB Windows 7 10 11",
        "category": "network",
        "tags": ["smb", "compartilhamento", "windows"],
        "content": "Problemas de SMB entre Windows 7/10/11 envolvem descoberta de rede, credenciais, firewall, versao SMB, permissao de pasta e politica de convidado. SMB1 e legado e deve ser evitado quando possivel.",
    },
    {
        "title": "Servidor RPC indisponivel",
        "category": "windows",
        "tags": ["rpc", "servico", "firewall"],
        "content": "Erro de servidor RPC indisponivel pode envolver servicos RPC/DCOM, firewall, DNS, conectividade, permissao remota e horario. Diagnostique rede e servicos antes de alterar politicas.",
    },
    {
        "title": "DNS com problema",
        "category": "network",
        "tags": ["dns", "internet", "rede"],
        "content": "Sintomas de DNS incluem ping por IP funcionando e nome falhando. Verifique DNS configurado, cache DNS, gateway, proxy, VPN e resolucao com servidores alternativos confiaveis.",
    },
    {
        "title": "IP 169.254 APIPA",
        "category": "network",
        "tags": ["169.254", "dhcp", "apipa"],
        "content": "IP 169.254 indica falha em obter DHCP. Verifique cabo/Wi-Fi, DHCP do roteador, conflito de driver, VLAN, firewall e tente renovar IP somente apos diagnostico.",
    },
    {
        "title": "Windows Update travado",
        "category": "windows",
        "tags": ["windows update", "travado"],
        "content": "Windows Update travado pede checar espaco em disco, servicos Windows Update/BITS, rede, hora correta e historico de erros. Limpeza de cache deve ser confirmada.",
    },
    {
        "title": "Disco 100 porcento",
        "category": "performance",
        "tags": ["disco 100", "lento", "performance"],
        "content": "Disco 100% pode indicar HD mecanico saturado, indexacao, Windows Update, antivirus, paginação, falha fisica ou processo pesado. Priorize identificar processo e saude do disco.",
    },
    {
        "title": "PC suspendendo sozinho",
        "category": "windows",
        "tags": ["energia", "suspensao"],
        "content": "Suspensao inesperada pode vir de plano de energia, bateria, superaquecimento, botao power, driver ACPI ou evento Kernel-Power. Verifique eventos e configuracoes de energia.",
    },
    {
        "title": "Notebook lento",
        "category": "performance",
        "tags": ["notebook", "lento", "ram", "ssd"],
        "content": "Notebook lento exige olhar CPU, RAM, disco, inicializacao, temperatura, antivirus, navegador, tipo de armazenamento e saude do SSD/HD. Acoes reversiveis primeiro.",
    },
    {
        "title": "Temperatura alta",
        "category": "hardware",
        "tags": ["temperatura", "cooler", "thermal"],
        "content": "Temperatura alta pode causar lentidao e desligamentos. Verifique poeira, pasta termica, ventoinha, obstrucao de saida de ar e carga de CPU/GPU.",
    },
    {
        "title": "Bateria notebook ruim",
        "category": "hardware",
        "tags": ["bateria", "notebook", "energia"],
        "content": "Bateria ruim aparece como queda rapida, desligamento sem aviso ou carga inconsistente. Use relatorio de bateria do Windows e confirme fonte/carregador.",
    },
    {
        "title": "Driver de video",
        "category": "hardware",
        "tags": ["gpu", "driver", "video"],
        "content": "Problemas de driver de video incluem tela preta, travamentos, baixa resolucao e erro de aceleracao. Prefira driver oficial do fabricante e restaure ponto se necessario.",
    },
    {
        "title": "Rede local nao acessa compartilhamento",
        "category": "network",
        "tags": ["rede local", "compartilhamento", "smb"],
        "content": "Falha ao acessar compartilhamento pode envolver perfil de rede publico, firewall, descoberta de rede, credenciais, permissao NTFS/compartilhamento, DNS/NetBIOS e SMB legado.",
    },
]


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_.-]+", text.lower()) if len(token) >= 3}


def _chunk_text(content: str, max_chars: int = 700) -> list[str]:
    paragraphs = [part.strip() for part in content.split("\n") if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs or [content]:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue
        for index in range(0, len(paragraph), max_chars):
            chunks.append(paragraph[index : index + max_chars])
    return chunks


def init_knowledge_base() -> None:
    if is_cloud() and not settings.rag_enabled:
        return
    init_agent_storage()
    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) AS total FROM knowledge_documents").fetchone()["total"]
        if count:
            sync_vector_store()
            return
        for item in INITIAL_KNOWLEDGE:
            index_json_knowledge(item, connection=connection)
        connection.commit()
    sync_vector_store()


def status() -> dict[str, Any]:
    if is_cloud() and not settings.rag_enabled:
        return {
            "enabled": False,
            "sqlite_fts_enabled": False,
            "documents": 0,
            "chunks": 0,
            "vector": {"enabled": False, "provider": "disabled"},
            "honest_status": "disabled_in_cloud_preview",
            "message": "RAG local desativado no cloud preview.",
        }
    vector_status = VectorMemoryStore().status()
    with get_connection() as connection:
        document_count = connection.execute("SELECT COUNT(*) AS total FROM knowledge_documents").fetchone()["total"]
        chunk_count = connection.execute("SELECT COUNT(*) AS total FROM knowledge_chunks").fetchone()["total"]
    return {
        "enabled": True,
        "sqlite_fts_enabled": True,
        "documents": document_count,
        "chunks": chunk_count,
        "vector": vector_status,
        "honest_status": "vector" if vector_status.get("enabled") else "sqlite-fts-fallback",
    }


def sync_vector_store() -> None:
    store = VectorMemoryStore()
    if not store.available:
        return
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT c.id, c.chunk_text, c.tags, d.id AS document_id, d.title, d.category, d.source
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.id = c.document_id
            """
        ).fetchall()
    items = [
        {
            "id": f"chunk-{row['id']}",
            "content": row["chunk_text"],
            "metadata": {
                "document_id": row["document_id"],
                "title": row["title"],
                "category": row["category"],
                "source": row["source"],
                "tags": row["tags"],
            },
        }
        for row in rows
    ]
    store.index(items)


def index_json_knowledge(item: dict[str, Any], connection=None) -> int:
    own_connection = connection is None
    if connection is None:
        connection = get_connection()
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    tags = item.get("tags", [])
    cursor = connection.execute(
        """
        INSERT INTO knowledge_documents
        (title, category, content, tags, source, version, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item["title"],
            item.get("category", "general"),
            item["content"],
            ",".join(tags),
            item.get("source", "seed-local"),
            item.get("version", "3.0.0"),
            now,
            now,
        ),
    )
    document_id = int(cursor.lastrowid)
    for index, chunk in enumerate(_chunk_text(item["content"])):
        chunk_cursor = connection.execute(
            """
            INSERT INTO knowledge_chunks (document_id, chunk_text, chunk_index, tags, score_boost)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, chunk, index, ",".join(tags), float(item.get("score_boost", 0))),
        )
        try:
            connection.execute(
                "INSERT INTO knowledge_chunks_fts(rowid, chunk_text, tags) VALUES (?, ?, ?)",
                (chunk_cursor.lastrowid, chunk, ",".join(tags)),
            )
        except Exception:
            pass
    if own_connection:
        connection.commit()
        connection.close()
    return document_id


def search(query: str, category: str | None = None, limit: int = 6) -> list[dict[str, Any]]:
    init_knowledge_base()
    vector_results = VectorMemoryStore().search(query, limit=limit)
    if vector_results:
        if category:
            vector_results = [item for item in vector_results if item.get("category") == category]
        if vector_results:
            return vector_results[:limit]
    try:
        results = _search_fts(query, category, limit)
        if results:
            return results
    except Exception:
        pass
    return _search_keywords(query, category, limit)


def _search_fts(query: str, category: str | None, limit: int) -> list[dict[str, Any]]:
    safe_query = " ".join(_tokenize(query))
    if not safe_query:
        return []
    sql = """
        SELECT d.id AS document_id, d.title, d.category, d.tags, d.source, c.chunk_text,
               bm25(knowledge_chunks_fts) AS bm25_score, c.score_boost
        FROM knowledge_chunks_fts
        JOIN knowledge_chunks c ON c.id = knowledge_chunks_fts.rowid
        JOIN knowledge_documents d ON d.id = c.document_id
        WHERE knowledge_chunks_fts MATCH ?
    """
    params: list[Any] = [safe_query]
    if category:
        sql += " AND d.category = ?"
        params.append(category)
    sql += " ORDER BY bm25_score LIMIT ?"
    params.append(limit)
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [
        {
            "document_id": row["document_id"],
            "title": row["title"],
            "category": row["category"],
            "content": row["chunk_text"],
            "tags": row["tags"],
            "source": row["source"],
            "score": round(1 / (1 + abs(float(row["bm25_score"]))) + float(row["score_boost"]), 4),
        }
        for row in rows
    ]


def _search_keywords(query: str, category: str | None, limit: int) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    with get_connection() as connection:
        if category:
            rows = connection.execute(
                """
                SELECT id, title, category, content, tags, source
                FROM knowledge_documents
                WHERE category = ?
                """,
                (category,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id, title, category, content, tags, source
                FROM knowledge_documents
                """
            ).fetchall()
    scored: list[dict[str, Any]] = []
    for row in rows:
        haystack = f"{row['title']} {row['content']} {row['tags']}"
        score = len(query_tokens & _tokenize(haystack))
        if score <= 0:
            continue
        scored.append(
            {
                "document_id": row["id"],
                "title": row["title"],
                "category": row["category"],
                "content": row["content"],
                "tags": row["tags"],
                "source": row["source"],
                "score": score,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def build_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines = []
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. {item['title']} [{item['category']}]: {item['content']}")
    return "\n".join(lines)
