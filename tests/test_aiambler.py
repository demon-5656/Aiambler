import pytest
import subprocess
import sys

from aiambler.compiler import PythonCompiler
from aiambler.errors import AccessDeniedError, UnknownFieldError
from aiambler.parser import AiamblerParser
from aiambler.runtime import AiamblerRuntime


def run_script(script: str):
    program = AiamblerParser().parse(script)
    runtime = AiamblerRuntime()
    return runtime.execute(program), runtime


def test_grouped_markdown_report_from_tz():
    result, runtime = run_script(
        """
        use b24 ro
        t = task? resp:15 status:open
        t |> group(project) |> sum(title,deadline,status,risk) |> out.md
        """
    )

    assert "Проект 1:" in result
    assert "title: Проверить гарантию" in result
    assert "Проект 2:" in result
    assert runtime.logs_as_dicts()[0]["risk_level"] == "read"


def test_ro_mode_blocks_write():
    with pytest.raises(AccessDeniedError) as exc:
        run_script(
            """
            use b24 ro
            b24.task.update id:123 stage:3199
            """
        )

    assert "ERR_ACCESS_DENIED" in str(exc.value)
    assert "b24.task.update" in str(exc.value)


def test_dry_run_write_preview_in_rw_mode():
    result, runtime = run_script(
        """
        use b24 rw
        dry
        b24.task.update id:123 stage:3199
        """
    )

    assert result == {
        "dry_run": True,
        "action": "update",
        "entity": "task",
        "id": 123,
        "changes": {"stage": 3199},
        "risk": "write",
        "requires_confirmation": True,
    }
    assert runtime.logs_as_dicts()[0]["dry_run"] is True


def test_gmail_pipeline_to_bitrix_create_dry_run():
    result, _runtime = run_script(
        """
        use gm ro
        use b24 rw
        dry
        mail? from:client after:7d |> has(deadline) |> b24.task+
        """
    )

    assert len(result) == 1
    assert result[0]["action"] == "create"
    assert result[0]["risk"] == "write"


def test_unknown_field_has_structured_error():
    with pytest.raises(UnknownFieldError) as exc:
        run_script(
            """
            use b24 ro
            task? resp:15 |> group(projectt)
            """
        )

    assert "ERR_UNKNOWN_FIELD" in str(exc.value)
    assert "field: projectt" in str(exc.value)


def test_compile_to_python_contains_connector_and_pipeline_calls():
    program = AiamblerParser().parse(
        """
        use b24 ro
        t = task? resp:15 status:open
        t |> group(project) |> out.md
        """
    )

    code = PythonCompiler().compile(program)

    assert "b24 = Connector('b24', mode='ro')" in code
    assert "t = b24.search('task', {'resp': 15, 'status': 'open'})" in code
    assert "print_output(group_by(t, 'project'), 'md')" in code


def test_compiled_python_executes_basic_pipeline():
    program = AiamblerParser().parse(
        """
        use b24 ro
        t = task? resp:15 status:open
        report = t |> group(project) |> out.md
        """
    )
    code = PythonCompiler().compile(program)
    namespace = {}

    exec(code, namespace)

    assert "Проект 1:" in namespace["report"]


def test_package_module_runs_ai_script_file(tmp_path):
    script = tmp_path / "script.ai"
    script.write_text(
        """
        use b24 ro
        t = task? resp:15 status:open
        t |> group(project) |> out.md
        """,
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-m", "aiambler", str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Проект 1:" in completed.stdout
