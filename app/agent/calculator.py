from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Callable


MAX_EXPRESSION_LENGTH = 120
MAX_AST_DEPTH = 20
MAX_ABS_RESULT = 1_000_000_000_000_000


@dataclass
class CalculationResult:
    ok: bool
    expression: str = ""
    display_expression: str = ""
    result: str = ""
    error: str = ""


def looks_like_calculation(text: str) -> bool:
    expression = extract_expression(text)
    return bool(expression and _has_operator(expression))


def calculate_expression(text: str) -> CalculationResult:
    expression = extract_expression(text)
    if not expression:
        return CalculationResult(ok=False, error="Nao encontrei uma expressao matematica clara.")

    try:
        normalized = normalize_expression(expression)
        tree = ast.parse(normalized, mode="eval")
        value = _eval_node(tree.body, depth=0)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("Resultado invalido.")
        if abs(float(value)) > MAX_ABS_RESULT:
            raise ValueError("Resultado grande demais para o calculo rapido.")
        return CalculationResult(
            ok=True,
            expression=normalized,
            display_expression=format_expression(normalized),
            result=format_number(value),
        )
    except ZeroDivisionError:
        return CalculationResult(ok=False, expression=expression, error="Divisao por zero.")
    except Exception as exc:
        return CalculationResult(ok=False, expression=expression, error=str(exc))


def extract_expression(text: str) -> str:
    candidate = text.strip().lower()
    if not candidate or len(candidate) > MAX_EXPRESSION_LENGTH:
        return ""

    candidate = candidate.replace("?", " ").replace("=", " ")
    candidate = _replace_word_operators(candidate)
    candidate = _strip_calculation_prefix(candidate)

    if _is_allowed_expression_text(candidate) and _has_operator(candidate):
        return candidate

    for match in re.finditer(r"[-+]?\d[\d\s.,+\-*/%^()xX×÷]*[\d)]", candidate):
        expression = match.group(0).strip()
        if _is_allowed_expression_text(expression) and _has_operator(expression):
            return expression
    return ""


def normalize_expression(expression: str) -> str:
    normalized = expression.strip()
    normalized = normalized.replace("×", "*").replace("÷", "/")
    normalized = re.sub(r"(?<=[\d)])\s*[xX]\s*(?=[\d(])", "*", normalized)
    normalized = re.sub(r"(?<=\d),(?=\d)", ".", normalized)
    normalized = normalized.replace("^", "**")
    normalized = re.sub(r"\s+", "", normalized)

    if len(normalized) > MAX_EXPRESSION_LENGTH:
        raise ValueError("Expressao longa demais.")
    if not re.fullmatch(r"[0-9.+\-*/%()]+", normalized):
        raise ValueError("Expressao contem caracteres nao permitidos.")
    return normalized


def format_expression(expression: str) -> str:
    display = expression.replace("**", "^")
    display = re.sub(r"([+\-*/%^])", r" \1 ", display)
    display = re.sub(r"\s+", " ", display).strip()
    display = display.replace("( ", "(").replace(" )", ")")
    return display


def format_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return f"{value:.10g}"


def _replace_word_operators(text: str) -> str:
    replacements = [
        (r"\bvezes\b", "*"),
        (r"\bmultipl(?:icado|ica)?\s+por\b", "*"),
        (r"\bdividido\s+por\b", "/"),
        (r"\bmais\b", "+"),
        (r"\bmenos\b", "-"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result


def _strip_calculation_prefix(text: str) -> str:
    prefixes = [
        r"quanto\s+(?:e|eh)\s+",
        r"calcule\s+",
        r"calcula\s+",
        r"calcular\s+",
        r"resultado\s+de\s+",
        r"qual\s+(?:e|eh)\s+o\s+resultado\s+de\s+",
    ]
    result = text.strip()
    for prefix in prefixes:
        result = re.sub(rf"^{prefix}", "", result).strip()
    return result


def _is_allowed_expression_text(text: str) -> bool:
    return bool(re.fullmatch(r"[\d\s.,+\-*/%^()xX×÷]+", text.strip()))


def _has_operator(text: str) -> bool:
    return bool(re.search(r"[+\-*/%^xX×÷]", text)) and len(re.findall(r"\d+", text)) >= 2


def _eval_node(node: ast.AST, depth: int) -> int | float:
    if depth > MAX_AST_DEPTH:
        raise ValueError("Expressao complexa demais.")

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Valor nao numerico bloqueado.")
        return node.value

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, depth + 1)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("Operador unario nao permitido.")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, depth + 1)
        right = _eval_node(node.right, depth + 1)
        operation = _operation_for(node.op)
        if isinstance(node.op, ast.Pow) and abs(float(right)) > 12:
            raise ValueError("Expoente alto demais para o calculo rapido.")
        value = operation(left, right)
        if abs(float(value)) > MAX_ABS_RESULT:
            raise ValueError("Resultado grande demais para o calculo rapido.")
        return value

    raise ValueError("Expressao nao permitida.")


def _operation_for(operator_node: ast.operator) -> Callable[[int | float, int | float], int | float]:
    operations: dict[type[ast.operator], Callable[[int | float, int | float], int | float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    operation = operations.get(type(operator_node))
    if not operation:
        raise ValueError("Operador nao permitido.")
    return operation
