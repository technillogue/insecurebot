import ast
import asyncio
import sys
import traceback
from typing import Any, Optional
from forest import core
from forest.core import Bot, Message, Response, rpc, run_bot


def is_admin(_: Message) -> bool:
    return True


core.is_admin = is_admin


class InsecureBot(Bot):
    async def do_eval(self, msg: Message) -> Response:
        """Evaluates a few lines of Python. Preface with "return" to reply with result."""

        async def async_exec(stmts: str, env: Optional[dict] = None) -> Any:
            parsed_stmts = ast.parse(stmts)
            fn_name = "_async_exec_f"
            my_fn = f"async def {fn_name}(): pass"
            parsed_fn = ast.parse(my_fn)
            for node in parsed_stmts.body:
                ast.increment_lineno(node)
            assert isinstance(parsed_fn.body[0], ast.AsyncFunctionDef)
            # replace the empty async def _async_exec_f(): pass body
            # with the AST parsed from the message
            parsed_fn.body[0].body = parsed_stmts.body
            code = compile(parsed_fn, filename="<ast>", mode="exec")
            exec(code, env or globals())  # pylint: disable=exec-used
            # pylint: disable=eval-used
            try:
                return await eval(f"{fn_name}()", env or locals())
            except:  # pylint: disable=bare-except
                return "".join(traceback.format_exception(*sys.exc_info()))

        if msg.full_text and len(msg.tokens) > 1:
            source_blob = msg.full_text.replace(msg.arg0, "", 1).lstrip("/ ")
            env = globals()
            env.update(locals())

            return str(await async_exec(source_blob, env))
        return None

    async def do_sh(self, msg: Message) -> str:
        return "\n".join(
            map(
                bytes.decode,
                filter(
                    lambda x: isinstance(x, bytes),
                    await (
                        await asyncio.create_subprocess_shell(
                            msg.text, stdout=-1, stderr=-1
                        )
                    ).communicate(),
                ),
            )
        )

    async def handle_message(self, message: Message) -> Response:
        if message.typing == "STARTED":
            await self.outbox.put(rpc("sendTyping", recipient=[message.source]))
        if message.typing == "STOPPED":
            await self.outbox.put(
                rpc("sendTyping", recipient=[message.source], stop=True)
            )
        return await super().handle_message(message)


if __name__ == "__main__":
    run_bot(InsecureBot)
