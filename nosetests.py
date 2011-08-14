from __future__ import print_function

import shlex
import subprocess
import filecmp
import shutil

ENV = {"DIFF": "/home/niklas/opt/diff/bin/diff"}


expected_normal_rescue = """
test/normal/known/importthis.txt
  0.9048 test/normal/rescue/file-matching-importthis.txt
  0.8636 test/normal/rescue/file-matching-importthis-less.txt
  0.0000 test/normal/rescue/quite-empty.txt
""".strip()

expected_normal_rescue_min_ratio = """
test/normal/known/importthis.txt
  0.9048 test/normal/rescue/file-matching-importthis.txt
  0.8636 test/normal/rescue/file-matching-importthis-less.txt
""".strip()


def test_normal_rescue_cmd():
	args = shlex.split("python filerescuematcher.py test/normal/known test/normal/rescue --mimetype-filter")
	out = subprocess.check_output(args, env=ENV)
	assert out.strip() == expected_normal_rescue

def test_normal_rescue_cmd_min_ratio():
	args = shlex.split("python filerescuematcher.py test/normal/known test/normal/rescue --mimetype-filter --min-ratio 0.7")
	out = subprocess.check_output(args, env=ENV)
	assert out.strip() == expected_normal_rescue_min_ratio

def test_normal_rescue_copy_dest():
	shutil.rmtree("test/normal/.copy-dest", ignore_errors=True)
	args = shlex.split("python filerescuematcher.py test/normal/known test/normal/rescue --mimetype-filter --copy-dest test/normal/.copy-dest")
	subprocess.check_output(args, env=ENV)
	assert filecmp.cmp("test/normal/rescue/file-matching-importthis.txt", "test/normal/.copy-dest/test/normal/known/importthis.txt")


def test_vcs_rescue_copy_dest():
	shutil.rmtree("test/vcs/.copy-dest", ignore_errors=True)
	args = shlex.split("python filerescuematcher.py test/vcs/known test/vcs/rescue --mimetype-filter --min-ratio 0.7 --copy-dest test/vcs/.copy-dest --copy-least-matching")
	subprocess.check_output(args, env=ENV)
	assert filecmp.cmp("test/vcs/rescue/file-matching-importthis-less.txt", "test/vcs/.copy-dest/test/vcs/known/importthis.txt")


def test_diff_error():
	if "diff (GNU diffutils) 3.0" in subprocess.check_output(["diff", "-v"]):
		args = shlex.split("python filerescuematcher.py test/normal/known test/normal/rescue --mimetype-filter --min-ratio 0.7")
		# Do not pass in DIFF env override
		try:
			out = subprocess.check_output(args, stderr=subprocess.STDOUT)
			assert False
		except subprocess.CalledProcessError as e:
			assert "diff lacks --ed-line-numbers-only option" in e.output
