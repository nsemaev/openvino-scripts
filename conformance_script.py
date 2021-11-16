import os
from os import path
import sys
import time
from datetime import datetime
import shutil
import subprocess
import _thread
import threading
from contextlib import contextmanager
import re
import xlsxwriter
from bs4 import BeautifulSoup


work_path = os.getcwd()
irs_path = '/home/nsemaev/Documents/ops/'
skipped_ops = ['boolean']
time_wasting_ops = ['Convolution', 'ConvolutionBackpropData', 'DeformableConvolution', 
					'GroupConvolution', 'GroupConvolutionBackpropData']
binary_path = f"{work_path}/conformanceTests"
ping_time = 60 * 5
run_results = ['passed', 'failed']
ci_results = ['passed', 'failed', 'skipped', 'crashed']

# kill -9 $(pgrep -f python3) && kill -9 $(pgrep -f conformanceTests)

all_ops = sorted(os.listdir(irs_path))
completed_ops = [op.split('_')[0] for op in os.listdir(work_path) if op.split('_')[-1] == 'completed']
logs_files = {}

class GTestParallel():
	def __init__(self, op: str):
		self.op = op
		self.op_path = f"{work_path}/{self.op}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"
		self.op_completed_path = f"{self.op_path}_completed"
		self.op_stopped_path = f"{self.op_path}_stopped"
		self.command = f"python3 {work_path}/gtest_parallel.py {binary_path} -d . " + \
			f"--gtest_filter=*ReadIRTest*{self.op}* " + \
			f"-- " + \
			f"--input_folders={irs_path}/{self.op} " + \
			f"--device=TEMPLATE " + \
			f"--report_unique_name " + \
			f"--output_folder={self.op_path}/gtest-parallel-xmls"
		self.report_command = f"python3 {work_path}/merge_xmls.py -i ./gtest-parallel-xmls/ -o ./"

	def run_while_not_end(self, op_time=30, time_limited=True):
		process_start_time = time.time()
		current_time = datetime.now().strftime('%Y_%m_%d %H:%M:%S')
		print(f"{current_time} {self.op} was started")
		print(self.command)
		if os.path.exists(self.op_path):
			shutil.rmtree(self.op_path)
		os.mkdir(self.op_path)
		os.chdir(self.op_path)
		threading.Thread(target=os.system, args=(f"cd {self.op_path} && {self.command}",)).start()
		# _thread.start_new_thread(os.system, (f"cd {self.op_path} && nohup {self.command}",))
		os.chdir(work_path)
		# statuses = ['passed', 'failed']
		start_time = time.time()
		last_ping = time.time()
		while True:
			time.sleep(1)
			if (os.path.exists(f"{self.op_path}/gtest-parallel-logs/passed")):
				break
			if (os.path.exists(f"{self.op_path}/gtest-parallel-logs/failed")):
				break
			if time_limited and (time.time() - start_time > 30):
				print(f"{datetime.now().strftime('%Y_%m_%d %H:%M:%S')} Sorry, time for operation {self.op} is over")
				os.rename(self.op_path, self.op_stopped_path)
				os.system('kill -9 $(pgrep -f conformanceTests)')
				return False
			if time.time() - last_ping > ping_time:
				print(f"{datetime.now().strftime('%Y_%m_%d %H:%M:%S')} {self.op} ping")
				last_ping = time.time()
		
		log_files_folder = f"{self.op_path}/gtest-parallel-logs/failed"
		failed_logs_result = f"{self.op_path}/{self.op}_failed_logs_result.txt"
		if os.path.exists(log_files_folder):
			with open(failed_logs_result, 'w', encoding='utf-8') as result_file:
				for log_file_name in os.listdir(log_files_folder):
					log_file_path = os.path.join(log_files_folder, log_file_name)  # !!! везде так же сделать

					# print(f"\n\n{log_file_path}\n\n")

					with open(log_file_path, 'r', encoding='utf-8') as file:
						data = str(file.read())
						test_filter = '/'.join(re.findall(r"Google Test filter = ([^\n]+)", data))
						mem_usage = '/'.join(re.findall(r"MEM_USAGE=([^\n]+)", data))
						failures = '/'.join(re.findall(r"[^\n]+pp:\s*\d+[^\n]+", data))
						# print(f"\n\n{test_filter}")
						# print(f"\n\n{mem_usage}")
						# print(f"\n\n{failures}")
						result_file.write(test_filter + ',')
						result_file.write(mem_usage + ',')
						result_file.write(failures + ';\n')
					# with open(log_path, 'r', encoding='utf-8') as file:
					# 	print(file.read())

		
		threading.Thread(target=os.system, args=(f"cd {self.op_path} && {self.report_command}",)).start()
		while (not os.path.exists(f"{self.op_path}/report.xml")):
			pass
		print(f"{datetime.now().strftime('%Y_%m_%d %H:%M:%S')} {self.op} was completed")
		self.op_completed_path = f"{self.op_path}_{int(time.time() - process_start_time)}s_completed"
		os.rename(self.op_path, self.op_completed_path)
		return True

# def autofit_xlsx(workbook_path: str):
# 	workbook = xlsxwriter.Workbook(workbook_path)
# 	worksheet = workbook

def generate_run_data():
	data = {}
	for i, op in enumerate(all_ops):
		run_folders = [folder for folder in os.listdir(work_path) 
					if folder.startswith(op) and folder.endswith('completed')]
		if run_folders:
			run_folder = sorted(run_folders)[-1]
			run_path = f"{work_path}/{run_folder}"
			data[op] = {}
			for result in run_results:
				result_path = f"{run_path}/gtest-parallel-logs/{result}"
				data[op][result] = len(os.listdir(result_path)) if path.exists(result_path) else 0

			failed_report = f"{run_path}/{op}_failed_logs_result.txt"
			if path.exists(failed_report):
				logs_files[op] = failed_report
		else:
			data[op] = {result: 'untested' for result in run_results}
	return data

def generate_ci_data():
	data = {}
	with open('report_dlb.html', 'r') as file:
		soup = BeautifulSoup(str(file.read()), 'html.parser')
	tbody = soup.findAll('tbody')[1]
	for op_tr in tbody.findAll('tr'):
		op = op_tr.findAll('th')[0].text.split('-')[0]
		template_td = op_tr.findAll('td')[0]
		data[op] = {result: 'untested' for result in ci_results}
		for result in data[op]:
			if len(template_td.find_all('span')) == 4:
				first_letter = result[0].upper()
				data[op][result] = int(re.findall(fr"{first_letter}:(\d+)", template_td.text)[0])
	return data

def get_from_TensorIterator_report(op: str):
	result = 'TensorIterator not tested'
	folders = [folder for folder in os.listdir(work_path) 
		if folder.split('_')[0] == 'TensorIterator' and folder.split('_')[-1] == 'completed']
	if folders:
		report_path = f"{work_path}/{sorted(folders)[-1]}/report.xml"
		with open(report_path, 'r', encoding='utf-8') as file:
			re_str = rf'<{op}-\d+ passed="\d+" failed="\d+" skipped="\d+" crashed="\d+" passrate="\d+\.\d+" />'
			result = ''.join(re.findall(re_str, file.read()))	
	return result

def generate_xlsx():
	columns = ['Operation', 'TensorIterator', 'Info', 'Group'] + \
				[f"RUN {result}" for result in run_results] + \
				[f"CI {result}" for result in ci_results] + ['RUN logs']
	columns_len = [len(column) for column in columns]
	run_data = generate_run_data()
	ci_data = generate_ci_data()
	ops = sorted(list(set(list(run_data.keys()) + list(ci_data.keys()))))

	# TODO: Delete operations that have 100% passrate in both lists, a better algorithm
	bad_ops = []
	for op in ops:
		flag = False
		if op in run_data:
			for result in run_results:
				if result not in ['passed']:
					if run_data[op][result] != 'untested' and int(run_data[op][result]) > 0:
						flag = True
						break
		if op in ci_data:
			for result in ci_results:
				if result not in ['passed']:
					if ci_data[op][result] != 'untested' and int(ci_data[op][result]) > 0:
						flag = True
						break
		if flag:
			bad_ops.append(op)
	ops = bad_ops

	workbook_path = f"{work_path}/{datetime.now().strftime('%Y_%m_%d__%H_%M_%S')}_report.xlsx"
	workbook = xlsxwriter.Workbook(workbook_path)
	worksheet = workbook.add_worksheet('report')
	for i, column in enumerate(columns):
		worksheet.write(0, i, column, workbook.add_format({"bold": True}))
	for i, op in enumerate(ops):
		shift = 0
		worksheet.write(i + 1, shift, op)
		columns_len[shift] = max(columns_len[shift], len(str(op)))
		shift += 1
		data = get_from_TensorIterator_report(op)
		if data is not None:
			worksheet.write(i + 1, shift, data)
		shift += 3
		if op in run_data:
			for j, result in enumerate(run_results):
				worksheet.write(i + 1, j + shift, run_data[op][result])
		shift += len(run_results)
		if op in ci_data:
			for j, result in enumerate(ci_results):
				worksheet.write(i + 1, j + shift, ci_data[op][result])
		shift += len(ci_results)
		if op in logs_files:
			with open(logs_files[op], 'r', encoding='utf-8') as file:
				worksheet.write(i + 1, shift, ''.join(file.readlines()))


	for i, column_len in enumerate(columns_len):
		if column_len > 0:
			worksheet.set_column(i, i, column_len)
	workbook.close()


if __name__ == '__main__1':
	ops = os.listdir(irs_path)
	# ops = ['Broadcast', 'Cos']  # 'AvgPool', 'Broadcast', 'Cos', 'boolean'
	bad_ops = ops
	for op in ops:
		if GTestParallel(op).run_while_not_end():
			bad_ops.remove(op)
	# if bad_ops:
	# 	print(f"bad ops: {', '.join(bad_ops)}")
	# 	print(bad_ops)

	for op in ops:
		if GTestParallel(op).run_while_not_end(15 * 60):
			bad_ops.remove(op)


if __name__ == '__main__':
	# print(get_from_TensorIterator_report('Add'))
	ops = [op for op in all_ops if op not in skipped_ops + completed_ops]
	for op in ops:
		GTestParallel(op).run_while_not_end(time_limited=False)
		generate_xlsx()
	generate_xlsx()

	# print(generate_run_data())
	# print(generate_ci_data())
	# generate_xlsx()
