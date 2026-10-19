"""Campos definidos por indicador e cálculo do valor a partir de uma fórmula (ex.: [Perdidas] / [Produzidas] * 100)."""
import ast
import operator
import re
from decimal import Decimal, DivisionByZero, InvalidOperation

_REF = re.compile(r'\[([^\[\]]+)\]')
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def lista_campos(ind):
    """Nomes dos campos do indicador (um por linha no cadastro), sem repetições."""
    vistos, saida = set(), []
    for linha in (ind.campos or '').splitlines():
        nome = linha.strip()
        if nome and nome.lower() not in vistos:
            vistos.add(nome.lower())
            saida.append(nome)
    return saida


def referencias(formula):
    return [r.strip() for r in _REF.findall(formula or '')]


def validar_formula(formula, campos):
    """Retorna mensagem de erro ou None."""
    if not (formula or '').strip():
        return None
    minusculos = {c.lower() for c in campos}
    for ref in referencias(formula):
        if ref.lower() not in minusculos:
            return f'A fórmula usa [{ref}], que não está na lista de campos.'
    try:
        calcular(formula, {c: Decimal(1) for c in campos})
    except ZeroDivisionError:
        pass
    except ValueError as e:
        return str(e)
    return None


def calcular(formula, dados):
    """Avalia a fórmula com os valores informados (dict nome -> Decimal). Só aceita + - * / e parênteses."""
    valores = {k.strip().lower(): v for k, v in dados.items()}

    def sub(m):
        chave = m.group(1).strip().lower()
        if chave not in valores or valores[chave] is None:
            raise ValueError(f'Campo sem valor: {m.group(1).strip()}')
        return f'({valores[chave]})'

    expr = _REF.sub(sub, formula)
    try:
        arvore = ast.parse(expr.strip(), mode='eval')
    except SyntaxError:
        raise ValueError('Fórmula inválida.')

    def avaliar(no):
        if isinstance(no, ast.Expression):
            return avaliar(no.body)
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
            return Decimal(str(no.value))
        if isinstance(no, ast.BinOp) and type(no.op) in _OPS:
            return _OPS[type(no.op)](avaliar(no.left), avaliar(no.right))
        if isinstance(no, ast.UnaryOp) and type(no.op) in _OPS:
            return _OPS[type(no.op)](avaliar(no.operand))
        raise ValueError('Fórmula inválida: use apenas números, [campos], + - * / e parênteses.')

    try:
        return avaliar(arvore).quantize(Decimal('0.01'))
    except (DivisionByZero, ZeroDivisionError):
        raise ZeroDivisionError('Divisão por zero na fórmula.')
    except InvalidOperation:
        raise ValueError('Resultado inválido.')
