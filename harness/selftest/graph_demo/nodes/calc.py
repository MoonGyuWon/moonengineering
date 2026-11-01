"""사칙연산만 안전하게 계산한다 (eval 을 쓰지 않는다)."""
import ast
import operator as op

OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.USub: op.neg}


def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_ev(n.left), _ev(n.right))
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_ev(n.operand))
    raise ValueError("사칙연산만 됩니다")


def run(state):
    v = _ev(ast.parse(state["q"], mode="eval").body)
    return {"result": int(v) if float(v).is_integer() else round(v, 6)}
