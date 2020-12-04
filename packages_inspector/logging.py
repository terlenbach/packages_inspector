import logging

import typer  # type: ignore


class ColorFormatter(logging.Formatter):
    colors = {
        "error": dict(fg="red"),
        "exception": dict(fg="red"),
        "critical": dict(fg="red"),
        "debug": dict(fg="blue"),
        "warning": dict(fg="yellow"),
    }

    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.lower()
        msg = record.getMessage()
        if level in self.colors:
            prefix = typer.style("{}: ".format(level), **self.colors[level])
            msg = "\n".join(prefix + x for x in msg.splitlines())
        return msg


class TyperHandler(logging.Handler):
    _use_stderr = True

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            typer.echo(msg, err=self._use_stderr)
        except Exception:
            self.handleError(record)
