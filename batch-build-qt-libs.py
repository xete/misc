#!/bin/python

# print "remove these warning and run!!"
exit(0)

# processing
import os
import re
import argparse
import platform

parser = argparse.ArgumentParser(description='build qt library modules in batch mode')
parser.add_argument('--projecttop', action='store', help='directory containing project files', default='')
parser.add_argument('--builddir', action='store', help='directory for building libraries', default='')
parser.add_argument('--deploydir', action='store', help='directory for deploying libraries', default='')
parser.add_argument('--qmakebin', action='store', help='qmake bin name (must be name that could be found in system PATH)', default='qmake')
parser.add_argument('--makebin', action='store', help='make bin name (must be name that could be found in system PATH,\'make\' on unix or \'mingw32-make\' on windows)', default='make')
parser.add_argument('--qmakespec', action='store', help='qmake spec', default='')
parser.add_argument('--dryrun', action='store_true', help='dry run')
parser.add_argument('--noreqmake', action='store_true', help='skip qmake step')
parser.add_argument('--noremake', action='store_true', help='skip make step')
parser.add_argument('--noinstall', action='store_true', help='skip install step')
args = parser.parse_args()


def search_project_files(project_files_top):
	pro_files_found = []
	cur_project_dir = ''
	for cur_dir_path, cur_dirs_list, cur_file_list in os.walk(project_files_top):
		if cur_dir_path.find('.git') != -1:
			continue
		if cur_project_dir != '' and cur_dir_path.startswith(cur_project_dir):
			continue
		cur_project_dir = ''
		for file_item in cur_file_list:
			if file_item.endswith('.pro'):
				cur_project_dir = cur_dir_path
				pro_files_found.append(cur_project_dir + PATH_SEPERATOR + file_item)
	return pro_files_found

def search_deployment_makefiles(makefiles_top, excluded_dirs = []):
	deployment_makefiles_found = []
	for cur_dir_path, cur_dirs_list, cur_file_list in os.walk(makefiles_top):
		for file_item in cur_file_list:
			try: 
				if excluded_dirs.index(cur_dir_path) >= 0:
					continue
			except:
				if file_item.find('Makefile') == -1:
					continue
				file_item = cur_dir_path + PATH_SEPERATOR + file_item
				deployment_makefiles_found.append(file_item)
	return deployment_makefiles_found

def find_longest_part(str1, str2):
	result = ""
	min_len = len(str1) if len(str1) <= len(str2) else len(str2)
	cur_find_idx = 0
	while cur_find_idx < min_len:
		if str1[cur_find_idx] == str2[cur_find_idx]:
			result += str1[cur_find_idx]
		cur_find_idx += 1
	while len(result) > 0 and not result.endswith(PATH_SEPERATOR):
		result = result[:-1]
	return result

def ensure_dir(dir_path):
	if not os.path.exists(dir_path):
		os.makedirs(dir_path)

def execute(cmd, dry_run):
	if dry_run:
		print cmd
	else:
		print cmd
		os.system(cmd)

def write_lines_to_file(file_path, line_list):
	with open(file_path, "w") as f:
		f.truncate()
		for l in line_list:
			f.writelines(l)

def fix_makefile_msyshack(file_path, msh):
	mshe = re.escape(r'$(INSTALL_ROOT:@msyshack@%=%)')
	regexp_mshe = '.*?\s([^\s]*?' + mshe + '[^\s]*?)\s.*?$'
	msysqtprefix = ''	
	with open(file_path) as f:
		for l in f:
			mo = re.match(regexp_mshe, l)
			if mo:
				prefix = mo.group(1)
				if msysqtprefix == '':
					msysqtprefix = prefix
				else:
					msysqtprefix = find_longest_part(msysqtprefix, prefix)
	if msysqtprefix == '':
		return
	lines = []
	if not msh.endswith('\\'):
		msh = msh + '\\'
	with open(file_path) as f:
		for l in f:
			nl = l.replace(msysqtprefix, msh)
			lines.append(nl)
	write_lines_to_file(makefile, lines)

def find_header_src_dst_info(file_path):
	header_source_base = ''
	header_install_root = ''
	cur_section = ''
	with open(file_path) as f:
		for l in f:
			if l.strip() == '' and cur_section != '':
				cur_section = ''
			mo = re.match(r"^([^\s|\.]*)\: ", l)
			if mo:
				cur_section = mo.group(1)
			if cur_section == 'install_class_headers' or cur_section == 'install_gen_headers':
				mo = re.match(r".*?mkdir(?:\s\-p)?\s(.*?)\s.*?$", l)
				if mo:
					header_install_root = mo.group(1)
					if not header_install_root.endswith(PATH_SEPERATOR):
						header_install_root += PATH_SEPERATOR
			elif cur_section == 'install_targ_headers':
				mo = re.match(r".*?\-\$\(QINSTALL(?:_PROGRAM)?\)\s(.*?)\s(.*?)\s*$", l)
				if mo:
					header_src = mo.group(1)
					if header_src.startswith(build_dir_top):
						continue
					if header_source_base == '':
						header_source_base = header_src
					else:
						header_source_base = find_longest_part(header_source_base, header_src)
	return (header_source_base, header_install_root)

def fix_makefile_dst_dir(file_path, header_info, dry_run):
	lines = []
	hdr_trunc2full = {}
	cur_section = ''
	header_source_base, header_install_root = header_info
	with open(file_path) as file_to_fix:
		for l in file_to_fix:
			lines.append(l)
			if l.strip() == '' and cur_section != '':
				cur_section = ''
			mo = re.match(r"^([^\s|\.]*)\: ", l)
			if mo:
				cur_section = mo.group(1)
			if cur_section == 'install_targ_headers':
				mo = re.match(r"(.*?\-\$\(QINSTALL(?:_PROGRAM)?\))\s(.*?)\s(.*?)\n", l)
				if mo:
					header_src = mo.group(2)
					header_dst = mo.group(3)
					if header_src.startswith(build_dir_top):
						continue
					if header_src.startswith(header_source_base):
						header_src_relative = header_src[len(header_source_base):]
						header_dst_fixed = header_install_root + header_src_relative
						if header_dst != header_dst_fixed:
							hdr_trunc2full[os.path.basename(header_src_relative)] = header_src_relative
							lines[len(lines) - 1] = mo.group(1) + ' ' + header_src + ' ' + header_dst_fixed + '\n'
					continue
			if cur_section == 'install_targ_headers':
				mo = re.match(r"(.*?)(\-.*[strip|STRIP].*)\s(.*?)\n", l)
				if mo:
					header_dst = mo.group(3)
					if header_dst.startswith(header_install_root):
						header_dst_relative = header_dst[len(header_install_root):]
						if not hdr_trunc2full.has_key(header_dst_relative):
							lines[len(lines) - 1] = ''
							continue
						header_dst_fixed = header_install_root + hdr_trunc2full[header_dst_relative]
						cmd_fixed = mo.group(1) + '-$(STRIP) ' + header_dst_fixed + '\n'
						# lines[len(lines) - 1] = cmd_fixed
						lines[len(lines) - 1] = ''
					continue
			if cur_section == 'uninstall_targ_headers':
				mo = re.match(r"(.*?\-\$\(DEL_FILE\))((?:\s\-[^\-]+)*)\s(.*?)\n", l)
				if mo:
					header_dst = mo.group(3)
					if header_dst.startswith(header_install_root):
						header_dst_relative = header_dst[len(header_install_root):]
						if not hdr_trunc2full.has_key(header_dst_relative):
							continue
						header_dst_fixed = header_install_root + hdr_trunc2full[header_dst_relative]
						lines[len(lines) - 1] = mo.group(1) + mo.group(2) + ' ' + header_dst_fixed + '\n'
					continue
	write_lines_to_file(file_path, lines)

def fix_makefile_move(file_path, dry_run):
	lines = []
	with open(file_path) as file_to_fix:
		for l in file_to_fix:
			lines.append(l.replace("$(MOVE)", "$(COPY)"))
	write_lines_to_file(file_path, lines)

def chdir_install_makefile(working_dir, cmd, dry_run):
	os.chdir(working_dir)
	execute(cmd, dry_run)


print 'checking system variables'
system_name = platform.system().lower()
if system_name == 'linux':
	PATH_SEPERATOR = '/'
elif system_name == 'windows':
	PATH_SEPERATOR = '\\'
else:
	print '  system', system_name, 'not supported yet!'
	exit(0)	
print '  system:', system_name

script_dir = os.getcwd()
project_top = script_dir if args.projecttop == '' else args.projecttop
build_dir_top = (script_dir + PATH_SEPERATOR + 'build') if args.builddir == '' else args.builddir
deploy_dir_top = (script_dir + PATH_SEPERATOR + 'deploy') if args.deploydir == '' else args.deploydir
qmakebin = args.qmakebin
makebin = args.makebin
qmakespec = args.qmakespec if args.qmakespec != '' else 'win32-g++' if system_name == 'windows' else 'linux-arm-gnueabi-g++' 
dryrun = args.dryrun
noreqmake = args.noreqmake
noremake = args.noremake
noinstall = args.noinstall
print '  project_top:', project_top
print '  script_dir:', script_dir
print '  build_dir_top:', build_dir_top
print '  deploy_dir_top:', deploy_dir_top
print '  qmakebin:', qmakebin 
print '  makebin:', makebin 
print '  qmakespec:', qmakespec 
print '  noreqmake:', noreqmake
print '  noremake:', noremake
print '  noinstall:', noinstall
print ''

ensure_dir(build_dir_top)
ensure_dir(deploy_dir_top)

project_files_found = search_project_files(script_dir)

for project_file_found in project_files_found:
	project_basename = os.path.basename(project_file_found)
	project_dirname = os.path.dirname(project_file_found)
	project_name = project_basename.split('.')[0]
	build_dir = build_dir_top + PATH_SEPERATOR + project_name
	build_src_dir = build_dir + PATH_SEPERATOR + 'src'
	print ''
	print '===> process project: ' + project_basename
	print '     project path: ' + project_dirname
	print '     build_dir: ' + build_dir
	print '     build_src_dir: ' + build_src_dir

	ensure_dir(build_dir)
	os.chdir(build_dir)

	if not noreqmake:
		print '     create qmake files'
		execute('       ' + qmakebin + ' ' + project_file_found + ' -spec ' + qmakespec, dryrun)

	if not noremake:
		print '     create Makefiles and do compilations'
		execute('       ' + makebin + ' -j4', dryrun)

	print '     fix install paths'
	makefile_list = search_deployment_makefiles(build_src_dir, [ build_src_dir ])
	
	if len(makefile_list) == 0:
		print '       no makefile found, skipped'
		continue

	for makefile in makefile_list:
		print '     fix makefile', makefile
		header_source_base, header_install_root = find_header_src_dst_info(makefile)
		print '       header_source_base: ' + header_source_base
		print '       header_install_root: ' + header_install_root
		if header_source_base.strip() == '' or header_install_root.strip() == '':
			print '       skip as source base or install root not found'
			continue
		print '       update Makefile:', makefile
		fix_makefile_dst_dir(makefile, (header_source_base, header_install_root), dryrun)
		fix_makefile_move(makefile, dryrun)
		if system_name == 'windows':
			fix_makefile_msyshack(makefile, deploy_dir_top)

	if not noinstall:
		print '     install'
		for makefile in makefile_list:
			makefile_basename = os.path.basename(makefile)
			if system_name == 'windows' and makefile_basename.lower() == 'makefile' and len(makefile_list) != 1:
				print '       skip', makefile
				continue
			print '       install', makefile
			local_var = ('INSTALL_ROOT=' + deploy_dir_top + ' ') if system_name == 'linux' else ''
			chdir_install_makefile(os.path.dirname(makefile),  local_var + makebin + ' -r -k -f \"' + makefile_basename + '\" install', dryrun)

