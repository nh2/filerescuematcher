#!/usr/bin/env python

import sys
import os

if sys.version_info < (3,2):
	sys.stderr.write("Python >= 3.2 required\n")
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
		die("diff lacks --ed-line-numbers-only option!")

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
	# return (type, start, end or None)
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
	proc = subprocess.Popen([DIFF_PROGRAM, "--ed-line-numbers-only", left_path, right_path], stdout=subprocess.PIPE)
	out, err = proc.communicate()
	if proc.returncode in (0,1):
		return out
	else:
		raise DiffError(proc.returncode)


def common_lines_ratio(left_path, right_path):
	""" What fraction of their lines l and r have in common. """
	ed_output_lines = diff_ed_lines(left_path, right_path).decode("utf-8").strip().split('\n')
	ed_lines = list(map(parse_diff_ed_line_number_header, ed_output_lines))
	deleted_lines = sum( ed_line.size for ed_line in ed_lines if ed_line.type in ('c','d') )
	# open in binary mode to prevent Python 3's platform-dependent encoding (e.g. utf-8)
	left_length = len(open(left_path, 'rb').readlines())
	right_length = len(open(right_path, 'rb').readlines())
	common_lines = left_length - deleted_lines
	ratio = 2.0 * common_lines / (left_length + right_length)
	return ratio


class CachingDict(dict):
	def get_or_cache(self, key, val_fn):
		cached = self.get(key)
		if not cached:
			cached = val_fn()
			self[key] = cached
		return cached


mime_cache = CachingDict()
def mimetype(path):
	import subprocess
	mime_fn = lambda: subprocess.check_output(["file", "-ib", path]).decode("utf-8").split(";")[0]
	return mime_cache.get_or_cache(path, mime_fn)

def build_file_list(dir):
	paths = []
	for dirpath, dirnames, filenames in os.walk(dir):
		for filename in filenames:
			path = os.path.join(dirpath, filename)
			paths.append(path)
	return paths

def find_tree_matches(left, right, prematch_filter=None):
	left_paths = build_file_list(left)
	right_paths = build_file_list(right)

	class Match(namedtuple("Match", "ratio file")):
		def __lt__(self, o):
			return self.ratio < o.ratio

	for left_path in left_paths:
		best_match = Match(0.0, None)  # format: (best_ratio, best_right_path)
		#print("searching for best match for %s" % left_path)
		for right_path in right_paths:
			if prematch_filter is None or prematch_filter(left_path, right_path):
				#print("comparing %s with %s" % (left_path, right_path))
				try:
					ratio = common_lines_ratio(left_path, right_path)
					best_match = max(best_match, Match(ratio, right_path), key=lambda m: m.ratio)
					#print("ratio: ", ratio)
				except DiffError as e:
					explanation = ""
					if e.returncode == 2:
						explanation = " - Perhaps the files are binary files"
					print("Error: %s%s" % (e, explanation))
		yield left_path, best_match

def copy_full_path(src, dst):
	import shutil
	dst_dir = os.path.dirname(dst)
	if not os.path.exists(dst_dir):
		os.makedirs(dst_dir)
	shutil.copyfile(src, dst)

def mimetype_filter(left_path, right_path):
	return mimetype(left_path) == mimetype(right_path)

def main():
	check_diff_program_or_die()

	parser = argparse.ArgumentParser(description='Compares two trees of files and tells which ones from the left tree match best with which ones from the right tree.')
	parser.add_argument('left_tree', help='For each file in this tree, it will be tried to find a matching equivalent from right_tree.')
	parser.add_argument('right_tree', help='The tree in which matching files are searched for.')

	parser.add_argument('--min-ratio', type=float, default=0.0, help='Only print matching having a line match ratio >= MIN_RATIO')

	parser.add_argument('--mimetype-filter', dest='mimetype_filter', action='store_true', help='Skip file matching if mimetypes do not match')

	parser.add_argument('--output-tree', metavar="DIR", help='If specified, matching files found in right_tree found are saved to DIR, where they get the same path/filename as their their equivalents from left_tree.')

	args = parser.parse_args()

	prematch_filters = []
	if(args.mimetype_filter):
		prematch_filters.append(mimetype_filter)

	def prematch_filter(left_path, right_path):
		return all( filter_fun(left_path, right_path) for filter_fun in prematch_filters )

	tree_matches = find_tree_matches(args.left_tree, args.right_tree, prematch_filter)

	for left_path, best_match in tree_matches:
		if best_match.ratio >= args.min_ratio:
			print("best match (%s) %s %s" % (best_match.ratio, left_path, best_match.file))
			if args.output_tree:
				copy_full_path(best_match.file, os.path.join(args.output_tree, left_path))

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		exit(1)
