from click.testing import CliRunner

import gptme.cli

def test_main():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(gptme.cli.main, ['--help'])
        assert result.exit_code == 0

def test_main_help():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(gptme.cli.main, ['.shell echo "yes"'])
        assert result.exit_code == 0
        assert 'yes\n' in result.output
