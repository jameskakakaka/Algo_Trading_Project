"""Offline regression guards for the publication security boundaries."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityConfigurationTests(unittest.TestCase):
    def test_unverified_compose_demo_cannot_define_runnable_services(self):
        compose = (ROOT/'docker/docker-compose.yml').read_text()
        active = '\n'.join(line.split('#', 1)[0] for line in compose.splitlines()).strip()
        self.assertEqual(active, 'services: {}',
                         'Kafka startup stays blocked until image and broker review is completed')

    def test_workflow_actions_require_official_sources_and_full_commit_pins(self):
        workflows = sorted((ROOT/'.github/workflows').glob('*.y*ml'))
        self.assertTrue(workflows)
        for workflow in workflows:
            references = re.findall(r'^\s*(?:-\s*)?uses:\s*([^\s#]+)',
                                    workflow.read_text(), re.MULTILINE)
            self.assertTrue(references, workflow.name)
            for reference in references:
                with self.subTest(workflow=workflow.name, action=reference):
                    self.assertRegex(
                        reference,
                        r'^actions/(checkout|setup-python|upload-artifact)@[0-9a-f]{40}$',
                        'New action sources/pins require an official provenance review')
