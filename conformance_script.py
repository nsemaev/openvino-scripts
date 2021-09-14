import os
import sys
import time
from datetime import datetime
import shutil
import subprocess
import _thread
import threading
from contextlib import contextmanager
import re

op_exceptions = ['boolean']
irs_path = '/home/nsemaev/Documents/ops/'
binary_path = '/home/nsemaev/CLionProjects/openvino/bin/intel64/Debug/conformanceTests'


class GTestParallel():
	def __init__(self, op: str):
		self.op = op
		self.execute_path = os.getcwd()
		self.op_path = f"{self.execute_path}/{self.op}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}"
		self.op_completed_path = f"{self.op_path}_completed"
		self.op_stopped_path = f"{self.op_path}_stopped"
		self.command = f"python3 {self.execute_path}/gtest_parallel.py {binary_path} -d . " + \
			f"--gtest_filter=*ReadIRTest*{self.op}* " + \
			f"-- " + \
			f"--input_folders={irs_path}/{self.op} " + \
			f"--device=TEMPLATE " + \
			f"--report_unique_name " + \
			f"--output_folder={self.op_path}/gtest-parallel-xmls"

	def run_while_not_end(self, op_time=30, time_limited=True):
		current_time = datetime.now().strftime('%Y_%m_%d %H:%M:%S')
		print(f"{current_time} {self.op} was started")
		print(self.command)
		exit 
		if os.path.exists(self.op_path):
			shutil.rmtree(self.op_path)
		os.mkdir(self.op_path)
		os.chdir(self.op_path)
		# sys.stdout = open(os.devnull, "w")
		# sys.stderr = open(os.devnull, "w")
		# with suppress_stdout():
		# 	print('HWLLO')
		threading.Thread(target=os.system, args=(f"cd {self.op_path} && {self.command}",)).start()
		# _thread.start_new_thread(os.system, (f"cd {self.op_path} && nohup {self.command}",))
		os.chdir(self.execute_path)
		# statuses = ['passed', 'failed']
		start_time = time.time()
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

				

		print(f"{datetime.now().strftime('%Y_%m_%d %H:%M:%S')} {self.op} was completed")
		os.rename(self.op_path, self.op_completed_path)
		return True

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
	ops = sorted([op for op in os.listdir(irs_path) if op not in op_exceptions])
	for op in ops:
		GTestParallel(op).run_while_not_end(time_limited=False)