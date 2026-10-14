"""High-level abstract syntax tree (AST) for decompiled WebAssembly expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


class ASTNode:
    """Base class for all AST nodes."""
    pass


class Expr(ASTNode):
    """Base class for expressions that evaluate to a value."""
    def to_c(self) -> str:
        raise NotImplementedError


class Statement(ASTNode):
    """Base class for statements that produce side effects."""
    def to_c(self, indent: int = 0) -> str:
        raise NotImplementedError


@dataclass
class Literal(Expr):
    value: int | float
    type_name: str = "i32"

    def to_c(self) -> str:
        return str(self.value)


@dataclass
class Variable(Expr):
    name: str

    def to_c(self) -> str:
        return self.name


@dataclass
class BinaryOp(Expr):
    op: str
    left: Expr
    right: Expr

    def to_c(self) -> str:
        l_str = self.left.to_c()
        r_str = self.right.to_c()
        return f"({l_str} {self.op} {r_str})"


@dataclass
class UnaryOp(Expr):
    op: str
    operand: Expr

    def to_c(self) -> str:
        return f"{self.op}({self.operand.to_c()})"


@dataclass
class CallExpr(Expr):
    func_name: str
    args: List[Expr] = field(default_factory=list)

    def to_c(self) -> str:
        args_str = ", ".join(a.to_c() for a in self.args)
        return f"{self.func_name}({args_str})"


@dataclass
class LoadExpr(Expr):
    type_name: str
    address: Expr
    offset: int = 0

    def to_c(self) -> str:
        addr_str = self.address.to_c()
        if self.offset != 0:
            return f"*({self.type_name}*)({addr_str} + {self.offset})"
        return f"*({self.type_name}*)({addr_str})"


@dataclass
class AssignStmt(Statement):
    target: str
    value: Expr

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        return f"{ind}{self.target} = {self.value.to_c()};"


@dataclass
class StoreStmt(Statement):
    type_name: str
    address: Expr
    value: Expr
    offset: int = 0

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        addr_str = self.address.to_c()
        val_str = self.value.to_c()
        if self.offset != 0:
            return f"{ind}*({self.type_name}*)({addr_str} + {self.offset}) = {val_str};"
        return f"{ind}*({self.type_name}*)({addr_str}) = {val_str};"


@dataclass
class ReturnStmt(Statement):
    value: Optional[Expr] = None

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        if self.value is not None:
            return f"{ind}return {self.value.to_c()};"
        return f"{ind}return;"


@dataclass
class ExprStmt(Statement):
    expr: Expr

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        return f"{ind}{self.expr.to_c()};"


@dataclass
class IfStmt(Statement):
    condition: Expr
    then_body: List[Statement] = field(default_factory=list)
    else_body: List[Statement] = field(default_factory=list)

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        lines = [f"{ind}if ({self.condition.to_c()}) {{"]
        for s in self.then_body:
            lines.append(s.to_c(indent + 1))
        if self.else_body:
            lines.append(f"{ind}}} else {{")
            for s in self.else_body:
                lines.append(s.to_c(indent + 1))
        lines.append(f"{ind}}}")
        return "\n".join(lines)


@dataclass
class LoopStmt(Statement):
    label: str
    body: List[Statement] = field(default_factory=list)

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        lines = [f"{ind}while (1) /* loop {self.label} */ {{"]
        for s in self.body:
            lines.append(s.to_c(indent + 1))
        lines.append(f"{ind}}}")
        return "\n".join(lines)


@dataclass
class BreakStmt(Statement):
    label: str

    def to_c(self, indent: int = 0) -> str:
        ind = "  " * indent
        return f"{ind}break /* to {self.label} */; "


@dataclass
class FunctionAST(ASTNode):
    name: str
    params: List[Tuple[str, str]]  # (name, type)
    return_type: str
    locals: List[Tuple[str, str]]
    body: List[Statement] = field(default_factory=list)

    def to_c(self) -> str:
        params_str = ", ".join(f"{t} {n}" for n, t in self.params)
        if not params_str:
            params_str = "void"
        lines = [f"{self.return_type} {self.name}({params_str}) {{"]

        for n, t in self.locals:
            lines.append(f"  {t} {n};")

        for s in self.body:
            lines.append(s.to_c(indent=1))

        lines.append("}")
        return "\n".join(lines)
