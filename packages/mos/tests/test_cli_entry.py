"""CLI entry exercises real main()."""

import json

from mos.cli import main


def test_cli_write_recall_status(capsys):
    assert main(["write", "--type", "semantic", "--content", "prefers dark mode UI", "--json"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["raw_ok"] is True

    assert main(["recall", "dark mode UI", "--intent", "preference_self", "--json"]) == 0
    recall = json.loads(capsys.readouterr().out)
    assert recall["count"] >= 1

    assert main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["ok"] is True
