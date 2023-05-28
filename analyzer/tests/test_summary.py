from analyzer import analyzer


class TestSummaryIV:
    def test_exit_code(self, runner, session):
        result = runner.invoke(analyzer, ["summary", "iv", "-w", "PD5"])
        assert result.exit_code == 0


class TestSummaryCV:
    def test_exit_code(self, runner, session):
        result = runner.invoke(analyzer, ["summary", "cv", "-w", "PD5"])
        assert result.exit_code == 0


class TestSummaryEQE:
    def test_exit_code(self, runner, session):
        result = runner.invoke(analyzer, ["summary", "eqe", "-w", "PD5"])
        assert result.exit_code == 0
