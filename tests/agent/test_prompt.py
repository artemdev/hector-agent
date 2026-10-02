from src.agent.prompt import make_prompt, repo_relative


class TestRepoRelative:
    def test_strips_the_reporting_machines_prefix(self, workdir, source_file):
        reported = f"/Users/me/projects/watchdog/fixtures/{source_file}"

        assert repo_relative(reported, workdir) == source_file

    def test_falls_back_to_file_name_when_not_in_clone(self, workdir):
        assert repo_relative("/srv/app/dist/server.js", workdir) == "server.js"

    def test_passes_through_missing_filename(self, workdir):
        assert repo_relative(None, workdir) is None


class TestMakePrompt:
    def test_describes_the_issue_with_a_repo_relative_file(self, workdir, source_file):
        event = {"data": {"issue": {
            "title": "ReferenceError: x is not defined",
            "culprit": "GET /",
            "metadata": {"filename": f"/Users/me/app/{source_file}", "value": "x is not defined"},
        }}}

        prompt = make_prompt(event, workdir)

        assert "- Title: ReferenceError: x is not defined" in prompt
        assert "- Culprit: GET /" in prompt
        assert f"- File: {source_file}" in prompt
        assert "- Details: x is not defined" in prompt
