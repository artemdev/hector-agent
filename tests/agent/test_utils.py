from src.agent.utils import repo_relative


class TestRepoRelative:
    def test_strips_the_reporting_machines_prefix(self, workdir, source_file):
        reported = f"/Users/me/projects/watchdog/fixtures/{source_file}"

        assert repo_relative(reported, workdir) == source_file

    def test_falls_back_to_file_name_when_not_in_clone(self, workdir):
        assert repo_relative("/srv/app/dist/server.js", workdir) == "server.js"

    def test_passes_through_missing_filename(self, workdir):
        assert repo_relative(None, workdir) is None
