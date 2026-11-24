import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "package/rill-runtime-manager/files/usr/libexec/rill-runtime-manager"
PACKAGE = ROOT / "package/rill-runtime-manager"


class RuntimeManagerPackageTests(unittest.TestCase):
    def invoke(
        self,
        method,
        *args,
        arch="x86_64",
        configure_ipk_feed=False,
        key_filename=None,
        installed_package="",
        installed_packages="",
        update_packages="",
        legacy_source=False,
        available_version="1.5.6-r7",
        release="24.10.8",
        runtime_binary_exists=False,
    ):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "etc").mkdir()
            (root / "var/lock").mkdir(parents=True)
            (root / "etc/openwrt_release").write_text(
                f'DISTRIB_RELEASE="{release}"\nDISTRIB_ARCH="{arch}"\n'
            )
            if runtime_binary_exists:
                runtime = root / "usr/bin/rill-runtime"
                runtime.parent.mkdir(parents=True)
                runtime.write_text("test runtime\n")
                runtime.chmod(0o755)
            if configure_ipk_feed:
                (root / "etc/opkg/keys").mkdir(parents=True)
                (root / "etc/opkg/customfeeds.conf").write_text(
                    "src/gz yun-openwrt "
                    "https://hello-yunshu.github.io/yun-openwrt-packages/24.10.8/x86_64/\n"
                    + (
                        "src/gz rill https://hello-yunshu.github.io/rill-openwrt-packages/preview/24.10.8/x86_64/\n"
                        if legacy_source
                        else ""
                    )
                )
                (root / "etc/opkg.conf").write_text("option check_signature\n")
                (root / "etc/opkg/keys" / key_filename).write_text("test public key\n")
            if release == "25.12.6":
                repositories = root / "etc/apk/repositories.d"
                repositories.mkdir(parents=True)
                (repositories / "yun.list").write_text(
                    "https://hello-yunshu.github.io/yun-openwrt-packages/25.12.6/"
                    f"{arch}/packages.adb\n"
                )
                keys = root / "etc/apk/keys"
                keys.mkdir(parents=True)
                (keys / "yun-feed.rsa.pub").write_text("test public key\n")
            bindir = root / "bin"
            bindir.mkdir()
            opkg = bindir / "opkg"
            opkg.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  status)\n"
                "    case \" ${TEST_INSTALLED_PACKAGES:-${TEST_INSTALLED_PACKAGE:-}} \" in *\" $2 \"*) printf 'Status: install user installed\\n'; exit 0;; esac\n"
                "    exit 1;;\n"
                "  list-installed)\n"
                "    case \" ${TEST_INSTALLED_PACKAGES:-${TEST_INSTALLED_PACKAGE:-}} \" in *\" $2 \"*) printf '%s - %s\\n' \"$2\" \"${TEST_CURRENT_VERSION:-1.5.6-r7}\"; exit 0;; esac\n"
                "    exit 0;;\n"
                "  list-upgradable)\n"
                "    case \" ${TEST_UPDATE_PACKAGES:-} \" in *\" $2 \"*) printf '%s - 1.0\\n' \"$2\";; esac; exit 0;;\n"
                "  list) if [ -n \"${TEST_CANDIDATE_VERSION:-}\" ]; then printf '%s - %s\\n' \"$2\" \"$TEST_CANDIDATE_VERSION\"; fi; exit 0;;\n"
                "  install) printf '%s\\n' \"$*\" >> \"${TEST_OPKG_LOG:-/dev/null}\"; exit 0;;\n"
                "  *) exit 0;;\n"
                "esac\n"
            )
            opkg.chmod(0o755)
            if configure_ipk_feed:
                usign = bindir / "usign"
                usign.write_text("#!/bin/sh\nprintf 'e58db45ab792599d\\n'\n")
                usign.chmod(0o755)
            if release == "25.12.6":
                apk = bindir / "apk"
                # Models apk-tools 3 as it actually behaves on 25.12:
                #   info -e <pkg>   installed?  (exit status only)
                #   info -v <pkg>   VERBOSE: prints the description, never a version
                #   list -I [pkg]   installed rows, "<name>-<version> <arch> ..."
                #   list -u [pkg]   upgradable rows; with no argument it dumps the
                #                   whole system, which is how the backend answers
                #                   three package questions from one query
                #   list -a <pkg>   all candidate rows from the configured feeds
                apk.write_text(
                    "#!/bin/sh\n"
                    "case \"$1\" in\n"
                    "  info)\n"
                    "    if [ \"$2\" = -e ]; then\n"
                    "      case \" ${TEST_INSTALLED_PACKAGE:-} \" in *\" $3 \"*) exit 0;; esac\n"
                    "      case \" ${TEST_INSTALLED_PACKAGES:-} \" in *\" $3 \"*) exit 0;; esac\n"
                    "      exit 1\n"
                    "    elif [ \"$2\" = -v ]; then\n"
                    "      printf '%s: Test package description.\\n' \"$3\"\n"
                    "      printf '%s: https://example.invalid/%s\\n' \"$3\" \"$3\"\n"
                    "      exit 0\n"
                    "    fi;;\n"
                    "  list)\n"
                    "    if [ \"$2\" = -u ]; then\n"
                    "      for p in ${TEST_UPDATE_PACKAGES:-}; do\n"
                    "        if [ -z \"${3:-}\" ] || [ \"$p\" = \"$3\" ]; then\n"
                    "          printf '%s-2.0.0-r0 x86_64 {test} (MIT) [upgradable from: %s-1.0.0-r0]\\n' \"$p\" \"$p\"\n"
                    "        fi\n"
                    "      done\n"
                    "    elif [ \"$2\" = -I ]; then\n"
                    "      for p in ${TEST_INSTALLED_PACKAGE:-} ${TEST_INSTALLED_PACKAGES:-}; do\n"
                    "        if [ -z \"${3:-}\" ] || [ \"$p\" = \"$3\" ]; then\n"
                    "          printf '%s-%s x86_64 {test} (MIT) [installed]\\n' \"$p\" \"${TEST_CURRENT_VERSION:-1.5.6-r7}\"\n"
                    "        fi\n"
                    "      done\n"
                    "    elif [ \"$2\" = -a ] && [ -n \"${TEST_CANDIDATE_VERSION:-}\" ]; then\n"
                    "      printf '%s-%s x86_64 {test} (MIT)\\n' \"$3\" \"$TEST_CANDIDATE_VERSION\"\n"
                    "    fi; exit 0;;\n"
                    "  add|upgrade) printf '%s\\n' \"$*\" >> \"${TEST_APK_LOG:-/dev/null}\"; exit 0;;\n"
                    "  update|fix) exit 0;;\n"
                    "  version) [ \"$2\" = -t ] && { [ \"$3\" = \"$4\" ] && echo '=' || echo '>'; }; exit 0;;\n"
                    "  *) exit 0;;\n"
                    "esac\n"
                )
                apk.chmod(0o755)
            env = os.environ.copy()
            env.update(
                RILL_MANAGER_TEST_ROOT=str(root),
                RILL_MANAGER_TESTING="1",
                TEST_INSTALLED_PACKAGE=installed_package,
                TEST_INSTALLED_PACKAGES=installed_packages,
                TEST_UPDATE_PACKAGES=update_packages,
                TEST_CURRENT_VERSION="1.5.6-r7",
                TEST_CANDIDATE_VERSION=available_version,
                TEST_OPKG_LOG=str(root / "opkg.log"),
                TEST_APK_LOG=str(root / "apk.log"),
                PATH=f"{bindir}:{env['PATH']}",
            )
            result = subprocess.run(
                [str(BACKEND), method, *args],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            parsed = json.loads(result.stdout)
            opkg_log = root / "opkg.log"
            if opkg_log.exists():
                parsed["_testOpkgLog"] = opkg_log.read_text()
            apk_log = root / "apk.log"
            if apk_log.exists():
                parsed["_testApkLog"] = apk_log.read_text()
            return result, parsed, root

    def test_package_is_noarch_and_never_owns_runtime_binary(self):
        makefile = (PACKAGE / "Makefile").read_text()
        package_definition = makefile.split("define Package/rill-runtime-manager\n", 1)[1].split("endef", 1)[0]
        install = makefile.split("define Package/rill-runtime-manager/install", 1)[1]
        self.assertIn("PKGARCH:=all", package_definition)
        self.assertRegex(makefile, r"define Build/Compile\s+:\s*endef")
        self.assertNotIn("/usr/bin/rill-runtime", install)
        self.assertNotIn("/usr/bin/rill-runtime", str(PACKAGE / "files"))

    def test_stable_preinstall_refuses_unowned_runtime_binary_and_conflicts_with_legacy(self):
        makefile = (ROOT / "package/rill-runtime/Makefile").read_text()
        self.assertIn("define Package/rill-runtime/preinst", makefile)
        self.assertIn("/usr/bin/rill-runtime", makefile)
        self.assertIn("PKG_UPGRADE", makefile)
        self.assertIn("opkg status rill-runtime", makefile)
        self.assertIn("apk info -e rill-runtime", makefile)
        self.assertIn("rill-runtime-preview", makefile)
        self.assertIn("refusing to overwrite", makefile)

    def test_status_reports_missing_configured_feed(self):
        result, payload, _ = self.invoke("status")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["errorCode"], "feed-not-configured")
        self.assertFalse(payload["feedReady"])
        self.assertTrue(payload["supported"])
        self.assertTrue(payload["helperAvailable"])
        self.assertFalse(payload["clientUpdateAvailable"])
        self.assertEqual(payload["runtimeUpdateAvailable"], payload["updateAvailable"])

    def test_status_exposes_pm_cfi_update_alias_contract(self):
        result, payload, _ = self.invoke(
            "status",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            installed_package="luci-app-performance-manager-all",
            update_packages="luci-app-performance-manager-all",
        )
        self.assertEqual(result.returncode, 0)
        for field in (
            "ok",
            "supported",
            "release",
            "architecture",
            "pkgtype",
            "installed",
            "channel",
            "version",
            "compatible",
            "updateAvailable",
            "runtimeUpdateAvailable",
            "clientUpdateAvailable",
            "cfiUpdateAvailable",
            "pmUpdateAvailable",
            "helperAvailable",
            "busy",
            "message",
            "errorCode",
        ):
            self.assertIn(field, payload)
        self.assertTrue(payload["helperAvailable"])
        self.assertTrue(payload["clientUpdateAvailable"])
        self.assertFalse(payload["cfiUpdateAvailable"])
        self.assertTrue(payload["pmUpdateAvailable"])
        self.assertEqual(payload["runtimeUpdateAvailable"], payload["updateAvailable"])

    def test_ipk_trust_key_uses_opkg_key_id_filename(self):
        correct, payload, _ = self.invoke(
            "status", configure_ipk_feed=True, key_filename="e58db45ab792599d"
        )
        self.assertEqual(correct.returncode, 0)
        self.assertTrue(payload["feedReady"])
        self.assertNotEqual(payload["errorCode"], "trust-key-missing")

        wrong, payload, _ = self.invoke(
            "status", configure_ipk_feed=True, key_filename="yun-openwrt-feed-usign.pub"
        )
        self.assertEqual(wrong.returncode, 0)
        self.assertFalse(payload["feedReady"])
        self.assertEqual(payload["errorCode"], "trust-key-missing")

    def test_legacy_rill_feed_blocks_unified_manager_actions(self):
        status, payload, _ = self.invoke(
            "status",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            legacy_source=True,
        )
        self.assertTrue(payload["feedReady"])
        self.assertEqual(payload["errorCode"], "legacy-feed-configured")

        action, payload, _ = self.invoke(
            "install",
            "rill-runtime",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            legacy_source=True,
        )
        self.assertNotEqual(action.returncode, 0)
        self.assertEqual(payload["errorCode"], "legacy-feed-configured")

    def test_legacy_preview_is_detected_and_never_replaced_implicitly(self):
        status, payload, _ = self.invoke(
            "status", configure_ipk_feed=True, key_filename="e58db45ab792599d",
            installed_package="rill-runtime-preview", runtime_binary_exists=True,
        )
        self.assertEqual(status.returncode, 0)
        self.assertTrue(payload["installed"])
        self.assertEqual(payload["channel"], "legacy-preview")
        self.assertEqual(payload["errorCode"], "legacy-runtime-migration-required")
        self.assertFalse(payload["updateAvailable"])

        for action in ("install", "update"):
            refused, payload, _ = self.invoke(
                action, "rill-runtime", configure_ipk_feed=True,
                key_filename="e58db45ab792599d",
                installed_package="rill-runtime-preview", runtime_binary_exists=True,
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(payload["errorCode"], "legacy-runtime-migration-required")
            self.assertNotIn("_testOpkgLog", payload)

    def test_legacy_preview_migration_state_blocks_consumer_management(self):
        result, payload, _ = self.invoke(
            "status",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            installed_packages="rill-runtime-preview luci-app-cloudflare-ip",
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(payload["repairAvailable"])
        self.assertEqual(payload["channel"], "legacy-preview")
        self.assertEqual(payload["errorCode"], "legacy-runtime-migration-required")

    def test_apk_update_detection_uses_real_upgradable_annotation(self):
        result, payload, _ = self.invoke(
            "status",
            release="25.12.6",
            installed_package="luci-app-cloudflare-ip",
            update_packages="luci-app-cloudflare-ip",
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(payload["feedReady"])
        self.assertTrue(payload["cfiUpdateAvailable"])
        self.assertFalse(payload["pmUpdateAvailable"])

    def test_consumer_update_pins_installed_runtime_on_ipk(self):
        result, payload, _ = self.invoke(
            "update",
            "luci-app-performance-manager-all",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            installed_packages="rill-runtime luci-app-performance-manager-all",
            update_packages="rill-runtime luci-app-performance-manager-all",
            runtime_binary_exists=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "install luci-app-performance-manager-all rill-runtime=1.5.6-r7",
            payload["_testOpkgLog"],
        )
        self.assertEqual(payload["runtimeUpdateAvailable"], payload["updateAvailable"])

    def test_consumer_update_pins_installed_runtime_on_apk(self):
        result, payload, _ = self.invoke(
            "update",
            "luci-app-cloudflare-ip",
            release="25.12.6",
            installed_packages="rill-runtime luci-app-cloudflare-ip",
            update_packages="rill-runtime luci-app-cloudflare-ip",
            runtime_binary_exists=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "upgrade luci-app-cloudflare-ip rill-runtime=1.5.6-r7",
            payload["_testApkLog"],
        )

    def test_consumer_update_without_runtime_fails_before_resolving_dependencies(self):
        result, payload, _ = self.invoke(
            "update",
            "luci-app-performance-manager-all",
            configure_ipk_feed=True,
            key_filename="e58db45ab792599d",
            installed_package="luci-app-performance-manager-all",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["errorCode"], "runtime-not-installed")
        self.assertNotIn("_testOpkgLog", payload)

    def test_unknown_package_is_rejected_before_package_manager(self):
        result, payload, _ = self.invoke("install", "busybox")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["errorCode"], "package-not-allowed")

    def test_runtime_is_not_supported_on_helper_only_architecture(self):
        result, payload, _ = self.invoke("status", arch="mipsel_24kc")
        self.assertFalse(payload["supported"])
        self.assertEqual(payload["errorCode"], "runtime-unsupported-architecture")


if __name__ == "__main__":
    unittest.main()
