"""Stack-based expression reconstructor and pseudocode generator."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from wasmlens.decompiler.ast import (
    AssignStmt,
    BinaryOp,
    BreakStmt,
    CallExpr,
    Expr,
    ExprStmt,
    FunctionAST,
    IfStmt,
    Literal,
    LoadExpr,
    LoopStmt,
    ReturnStmt,
    Statement,
    StoreStmt,
    UnaryOp,
    Variable,
)
from wasmlens.parser.types import FunctionBody, ValueType, WasmModule

# Map mnemonic to binary C operator
BINARY_OPS: Dict[str, str] = {
    "i32.add": "+",
    "i64.add": "+",
    "f32.add": "+",
    "f64.add": "+",
    "i32.sub": "-",
    "i64.sub": "-",
    "f32.sub": "-",
    "f64.sub": "-",
    "i32.mul": "*",
    "i64.mul": "*",
    "f32.mul": "*",
    "f64.mul": "*",
    "i32.div_s": "/",
    "i32.div_u": "/",
    "i64.div_s": "/",
    "i64.div_u": "/",
    "f32.div": "/",
    "f64.div": "/",
    "i32.rem_s": "%",
    "i32.rem_u": "%",
    "i64.rem_s": "%",
    "i64.rem_u": "%",
    "i32.and": "&",
    "i64.and": "&",
    "i32.or": "|",
    "i64.or": "|",
    "i32.xor": "^",
    "i64.xor": "^",
    "i32.shl": "<<",
    "i64.shl": "<<",
    "i32.shr_s": ">>",
    "i32.shr_u": ">>",
    "i64.shr_s": ">>",
    "i64.shr_u": ">>",
    "i32.eq": "==",
    "i64.eq": "==",
    "f32.eq": "==",
    "f64.eq": "==",
    "i32.ne": "!=",
    "i64.ne": "!=",
    "f32.ne": "!=",
    "f64.ne": "!=",
    "i32.lt_s": "<",
    "i32.lt_u": "<",
    "i64.lt_s": "<",
    "i64.lt_u": "<",
    "f32.lt": "<",
    "f64.lt": "<",
    "i32.le_s": "<=",
    "i32.le_u": "<=",
    "i64.le_s": "<=",
    "i64.le_u": "<=",
    "f32.le": "<=",
    "f64.le": "<=",
    "i32.gt_s": ">",
    "i32.gt_u": ">",
    "i64.gt_s": ">",
    "i64.gt_u": ">",
    "f32.gt": ">",
    "f64.gt": ">",
    "i32.ge_s": ">=",
    "i32.ge_u": ">=",
    "i64.ge_s": ">=",
    "i64.ge_u": ">=",
    "f32.ge": ">=",
    "f64.ge": ">=",
}


class Decompiler:
    """Decompiles WebAssembly bytecode into high-level structured C pseudocode."""

    def __init__(self, module: WasmModule) -> None:
        self.module = module

    def decompile_function(self, func_idx: int) -> str:
        ast = self.build_ast(func_idx)
        return ast.to_c()

    def build_ast(self, func_idx: int) -> FunctionAST:
        imported_count = self.module.imported_func_count
        if func_idx < imported_count:
            # Declaration only
            sig = self.module.get_function_type(func_idx)
            fn_name = self.module.get_function_name(func_idx)
            params = [(f"arg_{i}", p.to_wat()) for i, p in enumerate(sig.params)]
            ret_type = sig.results[0].to_wat() if sig.results else "void"
            return FunctionAST(name=fn_name, params=params, return_type=ret_type, locals=[])

        body_idx = func_idx - imported_count
        body = self.module.codes[body_idx]
        sig = self.module.get_function_type(func_idx)
        fn_name = self.module.get_function_name(func_idx)

        # Names
        params: List[Tuple[str, str]] = []
        for i, p in enumerate(sig.params):
            p_name = self._get_var_name(func_idx, i, is_param=True)
            params.append((p_name, p.to_wat()))

        # Locals
        locals_list: List[Tuple[str, str]] = []
        local_types = body.get_all_local_types()
        param_count = len(sig.params)
        for i, l_type in enumerate(local_types):
            idx = param_count + i
            l_name = self._get_var_name(func_idx, idx, is_param=False)
            locals_list.append((l_name, l_type.to_wat()))

        ret_type = sig.results[0].to_wat() if sig.results else "void"

        # Structured traversal
        body_stmts = self._reconstruct_block(func_idx, body.instructions, sig)
        return FunctionAST(
            name=fn_name,
            params=params,
            return_type=ret_type,
            locals=locals_list,
            body=body_stmts,
        )

    def _get_var_name(self, func_idx: int, local_idx: int, is_param: bool) -> str:
        if func_idx in self.module.local_names and local_idx in self.module.local_names[func_idx]:
            return self.module.local_names[func_idx][local_idx]
        if is_param:
            return f"arg_{local_idx}"
        return f"var_{local_idx}"

    def _reconstruct_block(
        self,
        func_idx: int,
        instructions: List[any],
        sig: any,
    ) -> List[Statement]:
        stack: List[Expr] = []
        statements: List[Statement] = []

        # Control block tracking
        # Each entry: { "type": "block"|"loop"|"if", "stmts": list, "stack": list, "cond": expr }
        control_stack: List[dict] = [{
            "type": "root",
            "stmts": statements,
            "stack": stack,
        }]

        for instr in instructions:
            curr = control_stack[-1]
            c_stack = curr["stack"]
            c_stmts = curr["stmts"]
            m = instr.mnemonic

            # 1. Constants
            if m.endswith(".const"):
                c_stack.append(Literal(value=instr.operands, type_name=m.split(".")[0]))

            # 2. Variable operations
            elif m == "local.get":
                v_name = self._get_var_name(func_idx, instr.operands, is_param=(instr.operands < len(sig.params)))
                c_stack.append(Variable(name=v_name))

            elif m == "local.set":
                v_name = self._get_var_name(func_idx, instr.operands, is_param=(instr.operands < len(sig.params)))
                val = c_stack.pop() if c_stack else Literal(0)
                c_stmts.append(AssignStmt(target=v_name, value=val))

            elif m == "local.tee":
                v_name = self._get_var_name(func_idx, instr.operands, is_param=(instr.operands < len(sig.params)))
                val = c_stack[-1] if c_stack else Literal(0)
                c_stmts.append(AssignStmt(target=v_name, value=val))

            elif m == "global.get":
                c_stack.append(Variable(name=f"global_{instr.operands}"))

            elif m == "global.set":
                val = c_stack.pop() if c_stack else Literal(0)
                c_stmts.append(AssignStmt(target=f"global_{instr.operands}", value=val))

            # 3. Binary operators
            elif m in BINARY_OPS:
                op = BINARY_OPS[m]
                right = c_stack.pop() if c_stack else Literal(0)
                left = c_stack.pop() if c_stack else Literal(0)
                c_stack.append(BinaryOp(op=op, left=left, right=right))

            # 4. Unary operators
            elif m.endswith(".eqz"):
                val = c_stack.pop() if c_stack else Literal(0)
                c_stack.append(UnaryOp(op="!", operand=val))

            # 5. Memory load & store
            elif ".load" in m:
                align, offset = instr.operands
                addr = c_stack.pop() if c_stack else Literal(0)
                type_name = m.split(".")[0]
                c_stack.append(LoadExpr(type_name=type_name, address=addr, offset=offset))

            elif ".store" in m:
                align, offset = instr.operands
                val = c_stack.pop() if c_stack else Literal(0)
                addr = c_stack.pop() if c_stack else Literal(0)
                type_name = m.split(".")[0]
                c_stmts.append(StoreStmt(type_name=type_name, address=addr, value=val, offset=offset))

            # 6. Function calls
            elif m == "call":
                target_fn_idx = instr.operands
                target_sig = self.module.get_function_type(target_fn_idx)
                call_args = []
                for _ in range(len(target_sig.params)):
                    if c_stack:
                        call_args.insert(0, c_stack.pop())
                    else:
                        call_args.insert(0, Literal(0))
                target_name = self.module.get_function_name(target_fn_idx)
                call_expr = CallExpr(func_name=target_name, args=call_args)
                if target_sig.results:
                    c_stack.append(call_expr)
                else:
                    c_stmts.append(ExprStmt(expr=call_expr))

            # 7. Control structures: block, loop, if
            elif m == "block":
                new_stmts: List[Statement] = []
                control_stack.append({
                    "type": "block",
                    "stmts": new_stmts,
                    "stack": c_stack,
                    "label": f"block_{len(control_stack)}",
                })

            elif m == "loop":
                new_stmts = []
                control_stack.append({
                    "type": "loop",
                    "stmts": new_stmts,
                    "stack": c_stack,
                    "label": f"loop_{len(control_stack)}",
                })

            elif m == "if":
                cond = c_stack.pop() if c_stack else Literal(1)
                then_stmts: List[Statement] = []
                else_stmts: List[Statement] = []
                control_stack.append({
                    "type": "if",
                    "cond": cond,
                    "stmts": then_stmts,
                    "then_stmts": then_stmts,
                    "else_stmts": else_stmts,
                    "in_else": False,
                    "stack": c_stack,
                })

            elif m == "else":
                if control_stack[-1]["type"] == "if":
                    control_stack[-1]["in_else"] = True
                    control_stack[-1]["stmts"] = control_stack[-1]["else_stmts"]

            elif m == "end":
                if len(control_stack) > 1:
                    popped = control_stack.pop()
                    parent_stmts = control_stack[-1]["stmts"]
                    p_type = popped["type"]

                    if p_type == "loop":
                        parent_stmts.append(LoopStmt(label=popped["label"], body=popped["stmts"]))
                    elif p_type == "block":
                        parent_stmts.extend(popped["stmts"])
                    elif p_type == "if":
                        parent_stmts.append(
                            IfStmt(
                                condition=popped["cond"],
                                then_body=popped["then_stmts"],
                                else_body=popped["else_stmts"],
                            )
                        )
                else:
                    # Closing end of function body
                    if c_stack and sig.results:
                        ret_val = c_stack.pop()
                        c_stmts.append(ReturnStmt(value=ret_val))

            elif m == "br":
                depth = instr.operands
                target_label = f"label_{depth}"
                c_stmts.append(BreakStmt(label=target_label))

            elif m == "br_if":
                depth = instr.operands
                cond = c_stack.pop() if c_stack else Literal(1)
                target_label = f"label_{depth}"
                c_stmts.append(IfStmt(condition=cond, then_body=[BreakStmt(label=target_label)]))

            elif m == "return":
                ret_val = c_stack.pop() if c_stack and sig.results else None
                c_stmts.append(ReturnStmt(value=ret_val))

            elif m == "drop":
                if c_stack:
                    c_stack.pop()

        return statements
