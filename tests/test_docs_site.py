"""Regression checks for documentation publishing configuration and source links."""

import importlib.util
import logging
import unittest
from pathlib import Path

import yaml

REPOSITORY = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("docs_link_processor", REPOSITORY / "docs/web/link_processor.py")
link_processor = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load docs/web/link_processor.py")
SPEC.loader.exec_module(link_processor)


class DocsSiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = yaml.safe_load((REPOSITORY / "docs/web/update-docs-config.yaml").read_text())

    def test_documentation_targets_are_unique(self) -> None:
        targets = {}
        for source, target, _weight in self.config["locations"]:
            if source.endswith("/"):
                entries = [
                    (str(path), Path(target) / ("_index.md" if path.name == "README.md" else path.name))
                    for path in (REPOSITORY / source).iterdir()
                    if path.suffix == ".md"
                ]
            else:
                entries = [(source, Path(target))]
            for origin, destination in entries:
                with self.subTest(destination=str(destination)):
                    if destination in targets:
                        self.fail(f"{origin} would overwrite {targets[destination]}")
                targets[destination] = origin

    def test_backup_relative_links_exist(self) -> None:
        source = REPOSITORY / "docs/backup.md"
        processor = link_processor.LinkProcessor(
            logging.getLogger(__name__),
            self.config["locations"],
            REPOSITORY,
            REPOSITORY / "docs/web/src/content",
            self.config["repository_url"],
        )
        for text, url in processor.extract_relative_links(source.read_text()):
            with self.subTest(text=text, url=url):
                if not processor.is_valid_link(source, url):
                    self.fail(f"Missing backup documentation target: {url}")


if __name__ == "__main__":
    unittest.main()
