#!/usr/bin/env python

# IDEAS
# - Make it work for binary files (not using whole lines to calculate the ratio)
# - Make it faster by using an index on the right tree, e.g. by putting 10-char snippets into a snippet-to-[file] dict

from __future__ import print_function

import sys
import os

if sys.version_info < (2,7) or (sys.version_info.major == 3 and sys.version_info < (3,2)):
	sys.stderr.write("Python 3 >= 3.2 or Python 2 >= 2.7 required\n")
	sys.exit(1)

import subprocess
import argparse
import difflib
import re
from collections import namedtuple


def die(msg, error_code=1):
	print("Error: " + msg, file=sys.stderr)
	exit(error_code)


DIFF_PROGRAM = os.environ.get('DIFF') or "diff"

def check_diff_program_or_die():
	if b"--ed-line-numbers-only" not in subprocess.check_output([DIFF_PROGRAM, "--help"]):
		die("diff lacks --ed-line-numbers-only option! Set the DIFF environment variable to a diff binary that supports this option.")


# Matches the ed hunk line headers in the output of diff -e, such as 12a, 12d, 12,15d, 12c, 12,15c. See http://www.gnu.org/s/diffutils/manual/#Detailed-ed
DIFF_ED_LINE_RE = re.compile(r"^(?P<start>\d+)(,(?P<end>\d+))?(?P<type>[a|c|d])$")

def parse_diff_ed_line_number_header(line):
	def die_invalid_input():
		die("Tried to parse invalid ed script line number header output: %s" % line)
	match = DIFF_ED_LINE_RE.match(line.strip())
	if match is None:
		die_invalid_input()
	match_dict = match.groupdict()
	# Check for illegal "\d+,\d+a" as our regex allows that
	if match_dict['type'] == 'a' and match_dict.get('end') is not None:
		die_invalid_input()
	start, end = match_dict['start'], match_dict.get('end')
	return EdDiffLine(match_dict['type'], int(start), int(end) if end else None)


class EdDiffLine(namedtuple('EdDiffLine', 'type start end')):
	@property
	def size(self):
		if self.end is None:
			return 1
		else:
			return self.end - self.start + 1


class DiffError(Exception):
	def __init__(self, returncode):
		Exception.__init__(self, "Got bad return code %s from diff" % returncode)
		self.returncode = returncode


def diff_ed_lines(left_path, right_path):
	"""
	Returns the output of diff --ed-line-numbers-only left_path right_path.
	Throws an exeption on a diff error, when the return code is not 0 or 1.
	"""
	proc = subprocess.Popen([DIFF_PROGRAM, "--ed-line-numbers-only", left_path, right_path], stdout=subprocess.PIPE)
	out, err = proc.communicate()
	if proc.returncode in (0,1):
		return out
	else:
		raise DiffError(proc.returncode)


def common_lines_ratio(left_path, right_path):
	"""
	What fraction of their lines l and r have in common.
	This is calculated as 2 * common_lines / (left_lines + right_lines).
	"""
	ed_output_lines = diff_ed_lines(left_path, right_path).decode("utf-8").strip().split('\n')
	ed_lines = list(map(parse_diff_ed_line_number_header, ed_output_lines))
	deleted_lines = sum( ed_line.size for ed_line in ed_lines if ed_line.type in ('c','d') )
	# open in binary mode to prevent Python 3's platform-dependent encoding (e.g. utf-8)
	left_lines = len(open(left_path, 'rb').readlines())
	right_lines = len(open(right_path, 'rb').readlines())
	common_lines = left_lines - deleted_lines
	ratio = 2.0 * common_lines / (left_lines + right_lines)
	return ratio


class CachingDict(dict):
	""" A simple key-value cache based on a dict. """
	def get_or_cache(self, key, val_fn):
		"""
		If key in self, return self[key].
		Otherwise set self[key] = val_fn() and return the calculated value.
		"""
		cached = self.get(key)
		if not cached:
			cached = val_fn()
			self[key] = cached
		return cached


class MimetypeCache(CachingDict):
	""" A file to mimetype cache """
	def mimetype(self, path):
		"""
		Returns the mimetype of the given path in the form of file -ib.
		Uses internal caching.
		"""
		import subprocess
		mime_fn = lambda: subprocess.check_output(["file", "-ib", path]).decode("utf-8").split(";")[0]
		return self.get_or_cache(path, mime_fn)


def build_file_list(dir):
	""" Returns a list of all files in the given directory as relative paths. """
	paths = []
	for dirpath, dirnames, filenames in os.walk(dir):
		for filename in filenames:
			path = os.path.join(dirpath, filename)
			paths.append(path)
	return paths


def find_tree_matches(left, right, prematch_filter=None, silent_diff_errors=False):
	"""
	Traverses the directories given as left and right, calculating the ratio of how similar each file in right is to each file in left.
	Runtime of no_files(left) * no_files(right).

	:param prematch_filter If given, all comparisons for which prematch_filter(left_file, right_file) is False are skipped.
	:param silent_diff_errors Prevent printing errors to stderr on bad diff return codes.
	"""
	left_paths = build_file_list(left)
	right_paths = build_file_list(right)

	for left_path in left_paths:
		matches = {}  # {right_path: ratio}
		for right_path in right_paths:
			if prematch_filter is None or prematch_filter(left_path, right_path):
				try:
					ratio = common_lines_ratio(left_path, right_path)
					matches[right_path] = ratio
				except DiffError as e:
					if not silent_diff_errors:
						explanation = ""
						if e.returncode == 2:
							explanation = " - Perhaps the files are binary files"
						print("Error: %s (for files %s and %s)%s" % (e, left_path, right_path, explanation), file=sys.stderr)
		yield left_path, matches


def copy_full_path(src, dst):
	""" Copies the file src to dst, recursively creating all parent directories of dst. """
	import shutil
	dst_dir = os.path.dirname(dst)
	if not os.path.exists(dst_dir):
		os.makedirs(dst_dir)
	shutil.copyfile(src, dst)


class MimetypeFilter(object):
	""" A filter to be passed into rescue_matcher that filters away all files which do not have the same mime type. """
	def __init__(self):
		self.mime_cache = MimetypeCache()
	def filter(self, left_path, right_path):
		return self.mime_cache.mimetype(left_path) == self.mime_cache.mimetype(right_path)


def rescue_matcher(left_tree, right_tree, min_ratio=0.0, prematch_filters=[], copy_dest=None, copy_least_matching=False):
	"""
	Compare all files in left_tree to all files in right_tree, and print out a ratio how similar they are to each other.
	
	:param min_ratio Ratio output is skipped for all files that have a common files ratio less than this.
	:param prematch_filters A list of objects having a filter() method. For all files (l, r) from (left_tree, right_tree) for which one of the filter()s returns false, comparison and ratio output of l and r are skipped.
	:param copy_dest The best matching from right_tree are copied to this directory, getting the file names of their best matching equivalents in left_tree.
	:param copy_least_matching If True, the file with the lowest ratio bigger than min_ratio is chosen as the best matching file for being copied to copy_dest. Ignored if copy_dest is None.
	"""

	# Filters out a file comparison if one of the prematch_filters filters it out
	def prematch_filter(left_path, right_path):
		return all( f.filter(left_path, right_path) for f in prematch_filters )

	tree_matches = find_tree_matches(left_tree, right_tree, prematch_filter)

	for left_path, matches_dict in tree_matches:
		# all matches >= min_ratio sorted by ratio in descending order
		selected_files = sorted(( k for k in matches_dict if matches_dict[k] >= min_ratio ), key=matches_dict.get, reverse=True)
		if selected_files:
			print("%s" % left_path)
			for right_path in selected_files:
				ratio = matches_dict[right_path]
				print("  %.4f %s" % (ratio, right_path))
			if copy_dest:
				best_match_path = selected_files[-1 if copy_least_matching else 0]
				copy_full_path(best_match_path, os.path.join(copy_dest, left_path))


def main():
	check_diff_program_or_die()

	parser = argparse.ArgumentParser(description='Compares two trees of files and tells which ones from the left tree match best with which ones from the right tree.')
	parser.add_argument('left_tree', help='For each file in this tree, it will be tried to find a matching equivalent from right_tree.')
	parser.add_argument('right_tree', help='The tree in which matching files are searched for.')

	parser.add_argument('--min-ratio', type=float, default=0.0, help='Only print matching having a line match ratio >= MIN_RATIO')

	parser.add_argument('--mimetype-filter', action='store_true', help='Skip file matching if mimetypes do not match. Can yield more useful results and speed up the matching process.')

	parser.add_argument('--copy-dest', metavar="DIR", help='If specified, matching files found in right_tree found are saved to DIR, where they get the same path/filename as their their equivalents from left_tree.')

	parser.add_argument('--copy-least-matching', action='store_true', help='Instead of copying the best matching file to the directory given in --copy-dest, copy the least matching one that exceeds MIN_RATIO. This is useful if there are different revisions of a file, with the most matching ones being oldest and the least matching ones the most recent ones (e.g. when a version control system was used).')

	args = parser.parse_args()

	# Handle argument confilcts
	if args.copy_dest is None and args.copy_least_matching:
		die("--copy-dest has to be specified for --copy-least-matching to take effect!")

	prematch_filters = []
	if(args.mimetype_filter):
		prematch_filters.append(MimetypeFilter())

	rescue_matcher(args.left_tree, args.right_tree, args.min_ratio, prematch_filters, args.copy_dest, args.copy_least_matching)


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		exit(1)
