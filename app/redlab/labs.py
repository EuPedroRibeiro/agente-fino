from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.redlab.models import LabBriefing, LabDifficulty


Matcher = Callable[[str], tuple[bool, str, str]]


def _contains(payload: str, patterns: tuple[str, ...], evidence: str, response: str) -> tuple[bool, str, str]:
    matched = any(pattern in payload.lower() for pattern in patterns)
    return matched, evidence if matched else "O teste nao atingiu a condicao vulneravel.", response if matched else "A aplicacao rejeitou o teste."


@dataclass(frozen=True)
class TrainingLab:
    id: str
    briefing: LabBriefing
    matcher: Matcher
    patch_diff: str
    regression_tests: tuple[str, ...]


LABS: tuple[TrainingLab, ...] = (
    TrainingLab(
        id="login_weak",
        briefing=LabBriefing(
            title="Login Fraco",
            description="Treine enumeracao e deteccao de credenciais previsiveis em um portal ficticio.",
            difficulty=LabDifficulty.EASY,
            category="authentication",
            objectives=["Identificar mensagem de erro enumeravel", "Encontrar a credencial ficticia do lab", "Aplicar rate limit e resposta uniforme"],
            hints=["O usuario administrativo e previsivel.", "Credenciais do lab nunca funcionam fora desta simulacao."],
            xp_reward=75,
        ),
        matcher=lambda payload: _contains(payload, ("admin:admin123", "admin:admin"), "Credencial ficticia aceita e usuario administrativo enumerado.", "Acesso administrativo simulado concedido."),
        patch_diff="+ rate_limit(5/min)\n+ resposta de autenticacao uniforme\n+ hash de senha forte",
        regression_tests=("bloqueia repeticao", "nao enumera usuario", "mantem login valido"),
    ),
    TrainingLab(
        id="idor_panel",
        briefing=LabBriefing(
            title="IDOR em Painel de Cliente",
            description="Analise um painel ficticio que confia em identificadores enviados pelo cliente.",
            difficulty=LabDifficulty.EASY,
            category="idor",
            objectives=["Alterar o identificador", "Detectar ausencia de autorizacao por objeto", "Aplicar verificacao de ownership"],
            hints=["Compare o recurso 1 com outro identificador."],
            xp_reward=90,
        ),
        matcher=lambda payload: _contains(payload, ("id=2", "client_id=2", "2"), "Objeto de outro cliente retornado sem verificacao de ownership.", "Registro ficticio de outro cliente exposto."),
        patch_diff="+ authorize_object(current_user, client_id)\n+ negar acesso cruzado",
        regression_tests=("permite objeto proprio", "nega objeto alheio", "registra tentativa"),
    ),
    TrainingLab(
        id="upload_guard",
        briefing=LabBriefing(
            title="Upload Inseguro",
            description="Teste validacao de extensao, MIME e armazenamento em um upload inteiramente simulado.",
            difficulty=LabDifficulty.MEDIUM,
            category="file_upload",
            objectives=["Detectar extensao executavel", "Identificar dupla extensao", "Aplicar armazenamento nao executavel"],
            hints=["Informe nome e conteudo separados por |."],
            xp_reward=130,
        ),
        matcher=lambda payload: _contains(payload, (".php|", ".asp|", ".jsp|", ".php5|"), "Arquivo executavel ficticio aceito pelo validador vulneravel.", "Upload simulado armazenado em area executavel."),
        patch_diff="+ allowlist de extensoes\n+ validar assinatura/MIME\n+ armazenar fora do webroot",
        regression_tests=("aceita imagem valida", "nega dupla extensao", "nega conteudo executavel"),
    ),
    TrainingLab(
        id="xss_comments",
        briefing=LabBriefing(
            title="Comentarios com XSS",
            description="Descubra falta de escaping em comentarios ficticios sem executar script no navegador.",
            difficulty=LabDifficulty.MEDIUM,
            category="cross_site_scripting",
            objectives=["Detectar markup perigoso", "Confirmar reflexao simulada", "Aplicar escaping e CSP"],
            hints=["Use uma tag de teste ou atributo de evento."],
            xp_reward=140,
        ),
        matcher=lambda payload: _contains(payload, ("<script", "onerror=", "onload=", "javascript:"), "Conteudo ativo seria renderizado sem escaping.", "Comentario refletido na simulacao vulneravel."),
        patch_diff="+ escape_html(comment)\n+ Content-Security-Policy restritiva\n+ sanitizacao allowlist",
        regression_tests=("escapa tag script", "remove evento inline", "mantem texto comum"),
    ),
    TrainingLab(
        id="sql_training",
        briefing=LabBriefing(
            title="Consulta SQL Injection",
            description="Identifique concatenacao insegura em uma consulta simulada, sem banco real vulneravel.",
            difficulty=LabDifficulty.HARD,
            category="sql_injection",
            objectives=["Detectar manipulacao da consulta", "Observar diferenca de resposta", "Aplicar consulta parametrizada"],
            hints=["A busca ficticia concatena o termo diretamente."],
            xp_reward=190,
        ),
        matcher=lambda payload: _contains(payload, ("' or ", "union select", "1=1", "--"), "A consulta ficticia foi alterada pelo valor informado.", "Resultados simulados excederam o escopo esperado."),
        patch_diff="+ cursor.execute(query, [term])\n+ conta com menor privilegio\n+ erros genericos",
        regression_tests=("parametriza aspas", "nao amplia resultados", "nao vaza erro SQL"),
    ),
    TrainingLab(
        id="exposed_admin",
        briefing=LabBriefing(
            title="Painel Admin Exposto",
            description="Investigue descoberta de rota administrativa ficticia e aplique controle de acesso.",
            difficulty=LabDifficulty.MEDIUM,
            category="admin_panel",
            objectives=["Localizar a rota ficticia", "Confirmar ausencia de autenticacao", "Aplicar autenticacao e autorizacao"],
            hints=["Rotas administrativas costumam usar nomes previsiveis."],
            xp_reward=120,
        ),
        matcher=lambda payload: _contains(payload, ("/admin", "/administrator", "/manage"), "Painel administrativo ficticio respondeu sem autenticacao.", "Configuracoes simuladas ficaram visiveis."),
        patch_diff="+ exigir sessao valida\n+ exigir role admin\n+ negar por padrao",
        regression_tests=("redireciona anonimo", "nega usuario comum", "permite admin"),
    ),
)

LABS_BY_ID = {lab.id: lab for lab in LABS}


def public_lab(lab: TrainingLab) -> dict:
    return {"id": lab.id, **lab.briefing.model_dump(mode="json")}
