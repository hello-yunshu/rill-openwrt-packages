from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.verify_sdk_feeds import inspect


class SDKFeedIdentity(unittest.TestCase):
    def check(self,base,packages,head='a'*40):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'feeds.conf.default').write_text(base+'\n'+packages+'\n')
            with patch('scripts.verify_sdk_feeds.subprocess.check_output',return_value=head+'\n'):
                return inspect(root)

    def test_release_tag_feed_and_full_commit_feed_remain_bound(self):
        data=self.check('src-git base https://example.invalid/openwrt.git;v24.10.8',
                        'src-git packages https://example.invalid/packages.git^'+'a'*40)
        self.assertEqual(set(data),{'base','packages'})
        self.assertEqual(data['base']['commit'],'a'*40)

    def test_sdk_root_option_is_not_a_feed_name(self):
        data=self.check('src-git --root=package base https://example.invalid/openwrt.git^'+'a'*40,
                        'src-git packages https://example.invalid/packages.git^'+'a'*40)
        self.assertEqual(set(data),{'base','packages'})
        self.assertTrue(data['base']['source'].endswith('^'+'a'*40))

    def test_unknown_options_and_stale_checkouts_cannot_pass(self):
        packages='src-git packages https://example.invalid/packages.git^'+'a'*40
        for base,head in [
            ('src-git --unknown=package base https://example.invalid/openwrt.git^'+'a'*40,'a'*40),
            ('src-git --root=package base https://example.invalid/openwrt.git^'+'a'*40,'b'*40),
        ]:
            with self.subTest(base=base),self.assertRaises(ValueError):self.check(base,packages,head)
