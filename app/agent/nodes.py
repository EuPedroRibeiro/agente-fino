from __future__ import annotations

from datetime import datetime
import json
import time
import unicodedata

from app.agent import rag
from app.agent.calculator import calculate_expression
from app.agent.evaluators.critic import Critic
from app.agent.evaluators.safety_checker import SafetyChecker
from app.agent.executor import prepare_pending_action
from app.agent.memory import AgentMemory
from app.agent.memory_stores.sqlite_memory import record_model_call
from app.agent.memory_stores.sqlite_memory import upsert_machine_profile
from app.agent.planner import create_plan
from app.agent.providers.model_router import ModelRouter
from app.agent.router import classify_message, is_direct_intent, is_simple_intent, web_needed
from app.agent.schemas.evidence import EvidenceItem
from app.agent.specialists.hardware_specialist import HardwareSpecialist
from app.agent.specialists.network_specialist import NetworkSpecialist
from app.agent.specialists.performance_specialist import PerformanceSpecialist
from app.agent.specialists.printer_specialist import PrinterSpecialist
from app.agent.specialists.security_specialist import SecuritySpecialist
from app.agent.specialists.web_research_specialist import WebResearchSpecialist
from app.agent.specialists.windows_specialist import WindowsSpecialist
from app.agent.tools_registry import get_tool, suggest_tools
from app.agent.web.cache import WebResearchCache
from app.agent.web.citations import make_citation
from app.agent.web.extractor import extract_text
from app.agent.web.fetcher import fetch_page
from app.agent.web.search import WebSearchEngine
from app.agent.web.verifier import WebEvidenceVerifier
from app.core.config import settings
from app.services.report import generate_technical_report
from app.services.system_info import get_health_payload, get_system_status


SPECIALISTS = {
    "printer": PrinterSpecialist(),
    "network": NetworkSpecialist(),
    "hardware": HardwareSpecialist(),
    "performance": PerformanceSpecialist(),
    "security": SecuritySpecialist(),
    "web_research": WebResearchSpecialist(),
    "windows": WindowsSpecialist(),
    "general": WindowsSpecialist(),
    "open_world": WindowsSpecialist(),
}


OFFICIAL_DOMAINS = [
    "learn.microsoft.com",
    "support.microsoft.com",
    "support.brother.com",
    "epson.com",
    "support.epson.net",
    "support.hp.com",
    "docs.python.org",
    "fastapi.tiangolo.com",
    "github.com",
    "nvd.nist.gov",
]


def normalize_input(state):
    normalized = " ".join(state.user_message.strip().split())
    state.normalized_message = normalized.lower()
    state.language = "pt-BR"
    state.urgency = "alta" if any(word in state.normalized_message for word in ["urgente", "parou", "sem internet", "critico"]) else "normal"
    state.requested_action = any(word in state.normalized_message for word in ["executa", "execute", "rode", "reinicia", "limpa", "baixa", "instala"])
    return state


def classify_intent(state):
    classification = classify_message(state.normalized_message)
    state.intent = classification["intent"]
    state.category = classification["category"]
    return state


def load_context(state, include_system_context: bool = True):
    state.system_context = {"health": get_health_payload()}
    should_load_status = state.intent == "system_metric_query" or (
        include_system_context and not is_direct_intent(state.intent)
    )
    if should_load_status:
        try:
            state.system_context["status"] = get_system_status()
        except Exception as exc:
            state.errors.append(f"Falha ao coletar status local: {exc}")
    if state.intent == "report_analysis":
        try:
            state.local_report = generate_technical_report(register_log=True, deep=False)
            hostname = state.local_report.get("summary", {}).get("hostname")
            if hostname:
                upsert_machine_profile(hostname, state.local_report)
            summary = state.local_report.get("summary", {})
            cpu = state.local_report.get("cpu", {})
            memory = state.local_report.get("memory", {})
            disk = state.local_report.get("disk", {})
            state.evidence.append(
                EvidenceItem(
                    source_type="local_report",
                    title="Relatorio tecnico local",
                    content=(
                        f"Host {summary.get('hostname')}; CPU {cpu.get('percent')}%; "
                        f"RAM {memory.get('percent')}%; disco {disk.get('percent')}%."
                    ),
                    score=1.0,
                    metadata={"summary": summary},
                )
            )
        except Exception as exc:
            state.errors.append(f"Falha ao gerar relatorio local: {exc}")
    return state


def decide_mode(state, use_web: bool = True, requested_mode: str = "auto"):
    if is_direct_intent(state.intent):
        state.mode = "DIRECT"
        state.system_context["provider"] = {
            "selected": "direct",
            "ollama_available": None,
            "openai_compatible_available": None,
            "local_rules_available": True,
        }
        return state

    router = ModelRouter()
    provider_status = router.status()
    if requested_mode and requested_mode.upper() in {"OFFLINE", "LOCAL_LLM", "WEB_AWARE", "HYBRID"}:
        state.mode = requested_mode.upper()
    elif use_web and settings.web_enabled:
        state.mode = "HYBRID" if provider_status["selected"] != "local-rules" else "WEB_AWARE"
    elif provider_status["selected"] != "local-rules":
        state.mode = "LOCAL_LLM"
    else:
        state.mode = "OFFLINE"
    state.system_context["provider"] = provider_status
    return state


def retrieve_memory(state):
    if is_direct_intent(state.intent) or state.intent == "web_research":
        return state
    memory = AgentMemory()
    state.memory_context = memory.search(state.user_id, state.normalized_message, limit=5)
    for item in state.memory_context[:3]:
        state.evidence.append(EvidenceItem(source_type="memory", title=item.get("title") or "Conversa anterior", content=item.get("content") or item.get("agent_response", ""), score=0.5))
    return state


def retrieve_knowledge(state):
    if is_direct_intent(state.intent) or state.intent == "web_research":
        return state
    category = state.category if state.category not in {"general", "web_research"} else None
    results = rag.search(state.normalized_message, category=category, limit=6)
    state.rag_context = results
    for item in results:
        state.evidence.append(EvidenceItem(source_type="rag", title=item["title"], content=item["content"], score=float(item.get("score", 0)), metadata={"category": item["category"], "source": item["source"]}))
    return state


def decide_web_need(state, use_web: bool = True):
    state.web_needed = bool(use_web and settings.web_enabled and web_needed(state.normalized_message, state.intent))
    return state


def web_research_if_needed(state):
    if not state.web_needed:
        return state
    research = perform_web_research(state.user_message, official_first=True, max_results=settings.web_max_results)
    state.web_used = research["web_used"]
    state.searched_at = research["searched_at"]
    state.web_context = research["results"]
    state.citations = research["sources"]
    for source in state.citations:
        state.evidence.append(EvidenceItem(source_type="web", title=source.title, content=source.excerpt, score=0.7, metadata=source.model_dump()))
    state.warnings.extend(research.get("warnings", []))
    return state


def specialist_analysis(state):
    if is_direct_intent(state.intent):
        state.risk_level = "low"
        state.system_context["specialist"] = {
            "specialist": "open_world",
            "diagnosis": "Conversa aberta sem necessidade de RAG, web ou ferramenta tecnica.",
            "signals": [],
        }
        state.system_context["specialist_questions"] = []
        state.system_context["specialist_safe_actions"] = []
        return state
    specialist = SPECIALISTS.get(state.category, SPECIALISTS["general"])
    analysis = specialist.analyze(state)
    state.system_context["specialist"] = analysis
    state.system_context["specialist_questions"] = specialist.suggest_questions(state)
    state.system_context["specialist_safe_actions"] = specialist.suggest_safe_actions(state)
    state.risk_level = specialist.risk_assessment(state)
    return state


def select_tools(state):
    if is_direct_intent(state.intent):
        state.selected_tools = []
        return state
    state.selected_tools = suggest_tools(state.category, state.intent)
    if state.web_needed and "search_web" not in state.selected_tools:
        state.selected_tools.append("search_web")
    if state.requested_action:
        if "spooler" in state.normalized_message:
            state.selected_tools.append("restart_spooler")
        elif "tempor" in state.normalized_message or "limpa" in state.normalized_message:
            state.selected_tools.append("clean_temp")
    state.selected_tools = list(dict.fromkeys(state.selected_tools))
    return state


def safety_check(state):
    result = SafetyChecker().check(state.normalized_message, state.selected_tools)
    state.risk_level = result["risk_level"]
    state.needs_confirmation = result["needs_confirmation"]
    if not result["allowed"]:
        state.final_answer = (
            "Nao posso executar ou orientar essa acao do jeito pedido, porque ela viola a politica de seguranca do Agente Fino. "
            "Posso analisar o conteudo de um script se voce colar aqui, explicar riscos e sugerir um caminho seguro sem executar nada."
        )
        state.confidence = 0.95
        state.warnings.append(result["reason"])
    elif state.needs_confirmation:
        for tool_name in state.selected_tools:
            tool = get_tool(tool_name)
            if tool and tool.requires_confirmation:
                pending = prepare_pending_action(state.user_id, tool_name)
                if pending:
                    state.pending_actions.append(pending)
    return state


def create_plan_node(state):
    if is_direct_intent(state.intent):
        state.plan = None
        return state
    state.plan = create_plan(state)
    return state


def generate_draft(state):
    if state.final_answer:
        state.draft_answer = state.final_answer
        return state
    if is_direct_intent(state.intent):
        state.draft_answer = _direct_answer(state)
        state.confidence = 0.98
        return state
    if state.intent == "report_analysis" and state.local_report:
        model_answer = _model_answer_if_available(state, _build_report_model_prompt(state), max_tokens=1400)
        state.draft_answer = model_answer or _report_analysis_answer(state)
        state.confidence = 0.86 if not model_answer else 0.9
        return state

    model_answer = _model_answer_if_available(state, _build_general_model_prompt(state), max_tokens=1200)
    if model_answer:
        state.draft_answer = model_answer
        state.confidence = _estimate_confidence(state) + 0.04
        return state

    specialist = state.system_context.get("specialist", {})
    rag_lines = [f"- {item['title']}: {item['content']}" for item in state.rag_context[:4]]
    evidence_lines = [f"- {item.title}: {item.content}" for item in state.evidence[:5]]
    memory_lines = [f"- {item.get('title') or item.get('user_message', 'Memoria')}" for item in state.memory_context[:3]]
    web_lines = [f"- {source.title} ({source.domain}, {source.reliability}, {source.source_status})" for source in state.citations[:5]]
    action_lines = [f"- {action['action_name']} exige confirmacao. ID: {action['id']}" for action in state.pending_actions]

    certainty = "Com base no contexto local"
    if state.web_used and state.rag_context:
        certainty += ", na base RAG e nas fontes web consultadas"
    elif state.web_used:
        certainty += " e nas fontes web consultadas"
    elif state.rag_context:
        certainty += " e na base RAG"

    answer_parts = [
        f"{certainty}, minha leitura inicial e: {specialist.get('diagnosis', 'diagnostico tecnico geral')}",
        "",
        "Diagnostico:",
        _diagnostic_text(state),
        "",
        "Evidencias usadas:",
        "\n".join(rag_lines or evidence_lines or ["- Nenhuma evidencia local forte encontrada."]),
    ]
    if memory_lines:
        answer_parts.extend(["", "Memoria relacionada:", "\n".join(memory_lines)])
    if web_lines:
        answer_parts.extend(["", "Fontes consultadas:", "\n".join(web_lines)])
    answer_parts.extend(["", "Plano seguro:", _plan_text(state)])
    if action_lines:
        answer_parts.extend(["", "Acoes pendentes:", "\n".join(action_lines), "Confirme explicitamente antes de executar."])
    if state.warnings:
        answer_parts.extend(["", "Alertas:", "\n".join(f"- {warning}" for warning in state.warnings)])
    state.draft_answer = "\n".join(answer_parts).strip()
    state.confidence = _estimate_confidence(state)
    return state


def verify_evidence(state):
    if is_direct_intent(state.intent):
        state.verified_answer = state.draft_answer
        return state
    if state.web_used:
        verification = WebEvidenceVerifier().verify(state.citations, sensitive_or_current=state.web_needed)
        state.warnings.extend(verification["warnings"])
    if state.web_needed and not state.citations:
        state.warnings.append("Web era recomendada, mas nenhuma fonte citavel foi obtida. Resposta limitada ao modo local.")
    state.verified_answer = state.draft_answer
    return state


def critic_review(state):
    if is_direct_intent(state.intent):
        return state
    review = Critic().review(state)
    state.warnings.extend(w for w in review["warnings"] if w not in state.warnings)
    state.confidence = review["confidence"]
    return state


def format_final(state):
    if state.final_answer and state.risk_level == "blocked":
        return state
    final = state.verified_answer or state.draft_answer
    if state.citations and "Fontes consultadas:" not in final:
        final += "\n\nFontes consultadas:\n" + "\n".join(f"- {source.title}: {source.url}" for source in state.citations)
    if state.warnings:
        unique = list(dict.fromkeys(state.warnings))
        final += "\n\nObservacoes de verificacao:\n" + "\n".join(f"- {warning}" for warning in unique)
    state.final_answer = final
    return state


def perform_web_research(query: str, official_first: bool = True, max_results: int = 8) -> dict:
    searched_at = datetime.now().astimezone().isoformat(timespec="seconds")
    cache = WebResearchCache()
    cached = cache.get(query)
    if cached and cached.get("sources"):
        from app.agent.schemas.evidence import SourceCitation

        return {
            "web_used": True,
            "searched_at": searched_at,
            "results": cached["results"],
            "sources": [SourceCitation(**item) for item in cached["sources"]],
            "warnings": ["Resultado retornado do cache web."],
        }

    engine = WebSearchEngine()
    official_domains = _official_domains_for_query(query)
    results = engine.search_official_first(query, official_domains) if official_first else engine.search(query, max_results=max_results)
    results = results[:max_results]
    citations = []
    fetched_results = []
    warnings = []
    for result in results[: settings.web_max_pages_fetch]:
        try:
            page = fetch_page(result.url)
            extracted = extract_text(page.text)
            excerpt = extracted.text[:700] or result.snippet
            citation = make_citation(
                title=extracted.title or result.title,
                url=page.final_url,
                excerpt=excerpt,
                fetched_at=page.fetched_at,
                used_for="pesquisa tecnica",
                source_status="lida",
            )
            citations.append(citation)
            fetched_results.append({**result.to_dict(), "extracted_title": extracted.title, "excerpt": excerpt})
        except Exception as exc:
            warnings.append(f"Nao foi possivel ler {result.url}: {exc}")
            citation = make_citation(
                title=result.title,
                url=result.url,
                excerpt=result.snippet,
                fetched_at=result.fetched_at,
                used_for="resultado de busca",
                source_status="resultado de busca, nao pagina lida",
            )
            citations.append(citation)
            fetched_results.append(result.to_dict())
    cache.set(query, [item.to_dict() for item in results], [item.model_dump() for item in citations])
    return {
        "web_used": bool(results),
        "searched_at": searched_at,
        "results": fetched_results or [item.to_dict() for item in results],
        "sources": citations,
        "warnings": warnings,
    }


def _diagnostic_text(state) -> str:
    if state.category == "printer":
        if "epson" in state.normalized_message and "driver" in state.normalized_message:
            return "Para driver da Epson L3250, prefira a pagina oficial da Epson do pais/regiao correto, confirme o sistema operacional detectado e evite baixar instaladores de sites de terceiros."
        if "brother" in state.normalized_message and "toner" in state.normalized_message:
            return "Em Brother com toner novo, confirme modelo exato, encaixe do cartucho, tampa, compatibilidade do consumivel, sensor e procedimento oficial antes de qualquer reset."
        return "Comece por modelo exato, consumivel/driver, status do spooler, fila e porta. Em Brother com toner novo, nao faca reset generico sem confirmar o modelo."
    if state.category == "network":
        return "Separe falha de IP, gateway, DNS e SMB. Um IP 169.254 indicaria DHCP falhando; DNS falha quando IP responde e nome nao."
    if state.category == "performance":
        if state.local_report:
            cpu = state.local_report.get("cpu", {}).get("percent", "indisponivel")
            ram = state.local_report.get("memory", {}).get("percent", "indisponivel")
            disk = state.local_report.get("disk", {}).get("percent", "indisponivel")
            top = state.local_report.get("top_processes", [])[:3]
            top_text = ", ".join(f"{item.get('name')} CPU {item.get('cpu_percent')}%" for item in top) or "sem top processos disponiveis"
            return f"Relatorio atual: CPU {cpu}%, RAM {ram}%, disco {disk}%. Top processos: {top_text}. Priorize confirmar o gargalo antes de executar limpeza ou reiniciar servicos."
        return "Correlacione CPU, RAM, disco e processos. Se disco ou CPU estiverem altos, primeiro identifique processo e evento antes de remover ou desativar algo."
    if state.intent == "command_request":
        return "Pedido envolve acao. O Agente Fino so trabalha com allowlist, confirmacao e registro."
    if state.intent == "web_research":
        if state.citations:
            return "Essa pergunta depende de informacao atual. Vou comparar fontes, priorizar documentacao oficial e separar recomendacao de opiniao."
        return "Essa pergunta depende de informacao atual. Ative a web ou refine a consulta para eu pesquisar fontes atuais e citar o que foi lido."
    return "Ainda preciso cruzar sintomas com contexto local. Acoes reversiveis e coleta de evidencia vem antes de qualquer mudanca."


def _direct_answer(state) -> str:
    if state.intent == "calculation_query":
        calculation = calculate_expression(state.user_message)
        if calculation.ok:
            return f"{calculation.display_expression} = {calculation.result}"
        return f"Nao consegui calcular isso com seguranca: {calculation.error}"
    if state.intent == "system_metric_query":
        return _system_metric_answer(state)
    return _simple_answer(state)


def _simple_answer(state) -> str:
    now = datetime.now().astimezone()
    text = _plain_text(state.normalized_message)
    if state.intent == "time_query":
        return f"Agora sao {now:%H:%M} no horario local deste PC ({now:%d/%m/%Y}, UTC{now:%z})."
    if state.intent == "date_query":
        return f"Hoje e {now:%d/%m/%Y}. Agora sao {now:%H:%M} no horario local deste PC."
    if state.intent == "identity_query":
        return (
            "Eu sou o Agente Fino. Posso conversar de forma aberta, tirar duvidas gerais, "
            "ajudar com tecnologia, analisar este PC, pesquisar na web com fontes e sugerir acoes seguras quando fizer sentido. "
            "Nao preciso transformar toda pergunta em diagnostico de equipamento."
        )
    if state.intent == "open_chat":
        provider = ModelRouter().selected_provider()
        if provider.name != "local-rules":
            response = provider.chat(
                [
                    {
                        "role": "system",
                        "content": "Voce e o Agente Fino. Responda como um assistente humano, direto, util e em portugues. Nao force diagnostico tecnico se a pergunta nao pedir.",
                    },
                    {"role": "user", "content": state.user_message},
                ],
                temperature=0.4,
                max_tokens=900,
            )
            if response.text:
                return response.text
        if _asks_how_i_am(text):
            return "Estou bem, sim. Meio ansioso para ficar mais inteligente, mas funcionando firme. E voce?"
        if _user_is_well(text):
            return "Boa. Fico feliz. Entao seguimos: conversa, projeto, diagnostico ou pesquisa, o que voce quiser puxar agora."
        if "obrigad" in text or "valeu" in text:
            return "Tamo junto. Pode mandar a proxima."
        return (
            "Entendi. Vou seguir contigo sem forcar diagnostico tecnico. "
            "No modo local eu sou mais direto, mas ainda consigo conversar, calcular, analisar o PC e pesquisar com fontes quando fizer sentido."
        )
    if _asks_how_i_am(text):
        return "Estou bem, sim. Pronto para continuar contigo. Como estao as coisas dai?"
    if _user_is_well(text):
        return "Boa. Que bom. Vamos nessa."
    if "obrigad" in text or "valeu" in text:
        return "Tamo junto. Pode mandar a proxima."
    return (
        "Oi! Estou aqui. Pode mandar a proxima."
    )


def _plain_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(stripped.replace("?", " ").replace("!", " ").split())


def _asks_how_i_am(text: str) -> bool:
    patterns = [
        "tudo bem",
        "como esta",
        "como voce esta",
        "como vc esta",
        "voce esta bem",
        "vc esta bem",
        "esta bem",
        "ta bem",
    ]
    return any(pattern in text for pattern in patterns)


def _user_is_well(text: str) -> bool:
    patterns = [
        "tudo otimo",
        "tudo certo",
        "estou bem",
        "to bem",
        "estou otimo",
        "otimo",
        "beleza",
        "tranquilo",
    ]
    return any(pattern in text for pattern in patterns)


def _model_answer_if_available(state, user_prompt: str, max_tokens: int = 1200) -> str:
    provider = ModelRouter().selected_provider()
    if provider.name == "local-rules":
        return ""

    started = time.perf_counter()
    response = provider.chat(
        [
            {
                "role": "system",
                "content": (
                    "Voce e o Agente Fino, um agente tecnico e conversacional em portugues do Brasil. "
                    "Responda de forma natural, objetiva e util. Nao invente dados. "
                    "Use apenas ferramentas ja executadas pelo backend; nunca diga que executou algo se nao executou. "
                    "Separe certeza, hipotese e proximo passo quando for diagnostico tecnico."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.35,
        max_tokens=max_tokens,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    record_model_call(
        user_id=state.user_id,
        conversation_id=state.conversation_id,
        provider=response.provider,
        model=response.model,
        used_model=response.used_model,
        latency_ms=latency_ms,
        success=response.used_model,
        error=None if response.used_model else response.text[:500],
    )
    state.system_context["model_call"] = {
        "provider": response.provider,
        "model": response.model,
        "used_model": response.used_model,
        "latency_ms": latency_ms,
    }
    if response.used_model and response.text:
        return response.text.strip()
    if response.text and response.provider != "local-rules":
        state.warnings.append(response.text[:300])
    return ""


def _build_report_model_prompt(state) -> str:
    report = state.local_report or {}
    compact_report = {
        "summary": report.get("summary"),
        "cpu": report.get("cpu"),
        "memory": report.get("memory"),
        "disk": report.get("disk"),
        "top_processes": report.get("top_processes", [])[:8],
        "services": report.get("services"),
        "printers": report.get("printers"),
        "network": report.get("network"),
        "observations": report.get("observations"),
    }
    return (
        "Analise este relatorio local do PC como um tecnico senior. "
        "Responda com: resumo direto, gargalos, evidencias, proximos testes e acoes seguras. "
        "Nao recomende executar comandos fora da allowlist.\n\n"
        f"Relatorio JSON compacto:\n{json.dumps(compact_report, ensure_ascii=False, indent=2)}"
    )


def _build_general_model_prompt(state) -> str:
    context = {
        "intent": state.intent,
        "category": state.category,
        "mode": state.mode,
        "rag": state.rag_context[:4],
        "memory": state.memory_context[:3],
        "web_sources": [source.model_dump() for source in state.citations[:5]],
        "local_report_available": bool(state.local_report),
        "selected_tools": state.selected_tools,
        "risk_level": state.risk_level,
    }
    return (
        f"Mensagem do usuario: {state.user_message}\n\n"
        f"Contexto disponivel:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Responda como um assistente inteligente de mundo aberto, sem forcar diagnostico se a pergunta for comum."
    )


def _report_analysis_answer(state) -> str:
    report = state.local_report or {}
    summary = report.get("summary", {})
    cpu = report.get("cpu", {})
    memory = report.get("memory", {})
    disk = report.get("disk", {})
    top_processes = report.get("top_processes", [])[:5]
    spooler = report.get("services", {}).get("print_spooler", {})
    observations = report.get("observations", [])

    top_lines = []
    for process in top_processes:
        top_lines.append(
            f"- {process.get('name', 'processo')} (PID {process.get('pid', '?')}): "
            f"CPU {process.get('cpu_percent', 'indisponivel')}%, RAM {process.get('memory_percent', 'indisponivel')}%"
        )

    alerts = []
    if isinstance(cpu.get("percent"), (int, float)) and cpu["percent"] >= 75:
        alerts.append("CPU esta em uso elevado no momento da coleta.")
    if isinstance(memory.get("percent"), (int, float)) and memory["percent"] >= 75:
        alerts.append("RAM esta em uso elevado; vale olhar os processos no topo.")
    if isinstance(disk.get("percent"), (int, float)) and disk["percent"] >= 80:
        alerts.append("Disco com uso alto; monitorar espaco livre e temporarios.")
    if spooler.get("status") not in {None, "running"}:
        alerts.append(f"Spooler de impressao esta como {spooler.get('status', 'indisponivel')}.")
    if not alerts:
        alerts.append("Nao vi gargalo critico imediato pelos dados coletados agora.")

    return "\n".join(
        [
            "Analise rapida deste PC:",
            "",
            f"- Host: {summary.get('hostname', 'indisponivel')}",
            f"- Sistema: {summary.get('operating_system', 'indisponivel')}",
            f"- Uptime: {summary.get('uptime', 'indisponivel')}",
            f"- CPU: {cpu.get('percent', 'indisponivel')}%",
            f"- RAM: {memory.get('percent', 'indisponivel')}% em uso ({memory.get('used_gb', 'indisponivel')} GB de {memory.get('total_gb', 'indisponivel')} GB)",
            f"- Disco {disk.get('path', 'C:')}: {disk.get('free_gb', 'indisponivel')} GB livres de {disk.get('total_gb', 'indisponivel')} GB ({disk.get('percent', 'indisponivel')}% usado)",
            f"- Spooler: {spooler.get('status', 'indisponivel')}",
            "",
            "Leitura tecnica:",
            *[f"- {item}" for item in alerts],
            *[f"- {item}" for item in observations[:3] if item not in alerts],
            "",
            "Processos em destaque:",
            *(top_lines or ["- Nenhum processo relevante retornado."]),
            "",
            "Proximos passos seguros:",
            "- Se o PC estiver lento, compare este retrato com outra coleta quando a lentidao acontecer.",
            "- Se impressao estiver falhando, validar spooler, fila e driver antes de reiniciar servico.",
            "- Para acao automatica, eu devo pedir confirmacao e usar somente ferramentas da allowlist.",
        ]
    )


def _system_metric_answer(state) -> str:
    status = state.system_context.get("status") or {}
    text = state.normalized_message
    if not status:
        return "Nao consegui ler o status do PC agora. Tenta de novo com 'Usar contexto do PC' ligado."

    disk = status.get("disk", {})
    memory = status.get("memory", {})
    cpu = status.get("cpu", {})

    if any(word in text for word in ["espaco", "espaço", "disco", "armazenamento", "hd", "ssd"]):
        return (
            f"No disco {disk.get('path', 'C:')}, voce tem {disk.get('free_gb', 'indisponivel')} GB livres "
            f"de {disk.get('total_gb', 'indisponivel')} GB. Uso atual: {disk.get('percent', 'indisponivel')}%."
        )
    if any(word in text for word in ["ram", "memoria", "memória"]):
        return (
            f"Sua RAM esta em {memory.get('percent', 'indisponivel')}% de uso: "
            f"{memory.get('used_gb', 'indisponivel')} GB usados de {memory.get('total_gb', 'indisponivel')} GB."
        )
    if any(word in text for word in ["cpu", "processador"]):
        return (
            f"A CPU esta em {cpu.get('percent', 'indisponivel')}% agora. "
            f"Nucleos: {cpu.get('physical_cores', 'indisponivel')} fisicos / {cpu.get('logical_cores', 'indisponivel')} logicos."
        )
    if "ip" in text:
        return f"O IP local deste PC e {status.get('local_ip') or 'indisponivel'}."
    if "hostname" in text or "nome do pc" in text:
        return f"O nome deste PC e {status.get('hostname') or 'indisponivel'}."
    if "uptime" in text or "tempo ligado" in text:
        return f"Este PC esta ligado ha aproximadamente {status.get('uptime') or 'indisponivel'}."

    return (
        f"Resumo rapido do PC: CPU {cpu.get('percent', 'indisponivel')}%, "
        f"RAM {memory.get('percent', 'indisponivel')}%, "
        f"disco {disk.get('percent', 'indisponivel')}% usado."
    )


def _plan_text(state) -> str:
    if not state.plan:
        return "- Coletar contexto\n- Comparar evidencias\n- Sugerir proximo teste"
    return "\n".join(f"- {step.title}: {step.detail}" for step in state.plan.steps[:6])


def _estimate_confidence(state) -> float:
    confidence = 0.45
    if state.rag_context:
        confidence += 0.18
    if state.memory_context:
        confidence += 0.08
    if state.citations:
        confidence += 0.2
    if state.local_report:
        confidence += 0.1
    if state.risk_level == "blocked":
        confidence = 0.95
    return min(confidence, 0.92)


def _official_domains_for_query(query: str) -> list[str]:
    text = query.lower()
    if "epson" in text:
        return ["epson.com.br", "epson.com", "epson.eu", "support.epson.net", "download-center.epson.com"]
    if "brother" in text:
        return ["support.brother.com", "brother.com"]
    if "hp" in text:
        return ["support.hp.com", "hp.com"]
    if "dell" in text:
        return ["dell.com"]
    if "lenovo" in text:
        return ["lenovo.com", "support.lenovo.com"]
    if "python" in text:
        return ["docs.python.org", "peps.python.org"]
    if "fastapi" in text:
        return ["fastapi.tiangolo.com"]
    if "cve" in text or "vulnerabilidade" in text:
        return ["nvd.nist.gov", "cve.org"]
    return OFFICIAL_DOMAINS
